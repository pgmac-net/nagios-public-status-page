"""Tests that the UTC storage invariant does not leak into the API contract.

Timestamps are timezone-aware UTC inside the application, but the JSON API has
always served naive strings that clients interpret as UTC. static/js/app.js
depends on that shape -- it appends 'Z' to any value containing 'T' that does
not already end in 'Z', so an offset-bearing payload would render as
'...+00:00Z' and parse as Invalid Date.
"""

import tempfile
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nagios_public_status_page.main import app
from nagios_public_status_page.models import Base, Comment, Incident


@pytest.fixture
def db_engine():
    """Create a temporary file-based database engine for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def db_session(db_engine):
    """Create a database session for testing."""
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    """Create a test client with the database dependency overridden."""
    from nagios_public_status_page.api.routes import get_db

    def override_get_db():
        Session = sessionmaker(bind=db_engine)
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_incident_timestamps_serialise_without_offset(client, db_session):
    """API timestamps carry no offset, exactly as before the UTC conversion.

    started_at etc. are relative to now, not a hardcoded date: /api/incidents
    defaults to a 24h "recent incidents" window, and a fixed calendar date ages
    out of it as soon as more than 24h pass since the fixture was written (#71).
    """
    started = datetime.now(UTC).replace(microsecond=0) - timedelta(hours=2)
    ended = started + timedelta(minutes=90)
    db_session.add(
        Incident(
            incident_type="host",
            host_name="k8s01",
            state=1,
            started_at=started,
            ended_at=ended,
            last_check=ended,
        )
    )
    db_session.commit()

    payload = client.get("/api/incidents").json()[0]

    assert payload["started_at"] == started.replace(tzinfo=None).isoformat()
    assert payload["ended_at"] == ended.replace(tzinfo=None).isoformat()
    assert payload["last_check"] == ended.replace(tzinfo=None).isoformat()
    for field in ("started_at", "ended_at", "last_check"):
        assert "+" not in payload[field]
        assert not payload[field].endswith("Z")


def test_null_timestamps_still_serialise_as_null(client, db_session):
    """An active incident's absent end time stays null, not a formatted string."""
    db_session.add(
        Incident(
            incident_type="host",
            host_name="k8s02",
            state=1,
            started_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    db_session.commit()

    payload = client.get("/api/incidents").json()[0]

    assert payload["ended_at"] is None


def test_to_dict_matches_api_serialisation(db_session):
    """Incident.to_dict() emits the same naive shape the API does."""
    incident = Incident(
        incident_type="service",
        host_name="k8s03",
        service_description="dqlite",
        state=2,
        started_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
    )
    db_session.add(incident)
    db_session.commit()

    assert incident.to_dict()["started_at"] == "2026-07-27T12:00:00"


def test_incident_written_in_non_utc_zone_serialises_as_utc(client, db_session):
    """A +10:00 value is normalised to UTC before it reaches the API.

    Without UTCDateTime, SQLite would store the wall clock unconverted and the
    API would serve a timestamp ten hours ahead of the real event time.
    """
    aest = timezone(timedelta(hours=10))
    started_utc = (datetime.now(UTC).replace(microsecond=0) - timedelta(hours=1))
    started_aest = started_utc.astimezone(aest)
    db_session.add(
        Incident(
            incident_type="host",
            host_name="macro",
            state=1,
            started_at=started_aest,
        )
    )
    db_session.commit()

    payload = client.get("/api/incidents").json()[0]
    assert payload["started_at"] == started_utc.replace(tzinfo=None).isoformat()


def test_incident_comparisons_hold_across_offsets(db_session):
    """Incidents recorded in different zones order by real time, not wall clock."""
    aest = timezone(timedelta(hours=10))
    earlier = Incident(
        incident_type="host",
        host_name="first",
        state=1,
        # 12:00 UTC, written as an AEST wall clock
        started_at=datetime(2026, 7, 27, 22, 0, tzinfo=aest),
    )
    later = Incident(
        incident_type="host",
        host_name="second",
        state=1,
        started_at=datetime(2026, 7, 27, 13, 0, tzinfo=UTC),
    )
    db_session.add_all([earlier, later])
    db_session.commit()
    db_session.expunge_all()

    ordered = (
        db_session.query(Incident).order_by(Incident.started_at.asc()).all()
    )

    assert [i.host_name for i in ordered] == ["first", "second"]
    assert ordered[0].started_at < ordered[1].started_at


def test_comment_links_to_incident_across_offsets(db_session):
    """Comment-to-incident time comparison survives a mixed-zone write."""
    aest = timezone(timedelta(hours=10))
    incident = Incident(
        incident_type="host",
        host_name="k8s01",
        state=1,
        started_at=datetime(2026, 7, 27, 12, 0, tzinfo=UTC),
        ended_at=datetime(2026, 7, 27, 14, 0, tzinfo=UTC),
    )
    db_session.add(incident)
    db_session.commit()

    # 23:00 AEST is 13:00 UTC, which falls inside the incident window.
    comment = Comment(
        incident_id=incident.id,
        author="paul",
        comment_text="investigating",
        created_at=datetime(2026, 7, 27, 23, 0, tzinfo=aest),
    )
    db_session.add(comment)
    db_session.commit()
    db_session.expunge_all()

    stored = db_session.query(Comment).one()
    incident = db_session.query(Incident).one()

    assert incident.started_at <= stored.created_at <= incident.ended_at


def test_naive_timestamp_is_rejected_at_the_model(db_session):
    """A naive datetime cannot reach storage, whichever model writes it."""
    db_session.add(
        Incident(
            incident_type="host",
            host_name="k8s01",
            state=1,
            # Deliberately naive: this is the value the model must reject.
            started_at=datetime(2026, 7, 27, 12, 0),  # noqa: DTZ001
        )
    )

    with pytest.raises(Exception, match="timezone-aware UTC"):
        db_session.commit()

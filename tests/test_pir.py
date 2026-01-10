"""Tests for Post-Incident Review (PIR) functionality."""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nagios_public_status_page.main import app
from nagios_public_status_page.models import Base, Incident


@pytest.fixture(scope="function")
def db_engine():
    """Create a temporary file-based database engine for testing."""
    # Create a temporary database file
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()

    # Clean up
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
    """Create a test client with database dependency override."""
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


@pytest.fixture
def sample_incident(db_session):
    """Create a sample incident for testing."""
    now = datetime.now()
    incident = Incident(
        incident_type="host",
        host_name="webserver01",
        service_description=None,
        state="DOWN",
        started_at=now - timedelta(hours=2),
        ended_at=now - timedelta(hours=1),
        last_check=now - timedelta(minutes=5),
        plugin_output="Host unreachable",
        post_incident_review_url=None,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)
    return incident


def test_incident_model_has_pir_field(db_session):
    """Test that Incident model has post_incident_review_url field."""
    now = datetime.now()
    incident = Incident(
        incident_type="service",
        host_name="webserver01",
        service_description="HTTP",
        state="CRITICAL",
        started_at=now,
        ended_at=None,
        post_incident_review_url=(
            "https://map.pgmac.net/incidents/2025-01-10-webserver01-http/"
        ),
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assert incident.post_incident_review_url == (
        "https://map.pgmac.net/incidents/2025-01-10-webserver01-http/"
    )


def test_incident_to_dict_includes_pir_url(db_session):
    """Test that incident to_dict() includes PIR URL."""
    now = datetime.now()
    incident = Incident(
        incident_type="host",
        host_name="dbserver01",
        service_description=None,
        state="DOWN",
        started_at=now,
        ended_at=None,
        post_incident_review_url=(
            "https://map.pgmac.net/incidents/2025-01-10-dbserver01/"
        ),
    )
    db_session.add(incident)
    db_session.commit()

    incident_dict = incident.to_dict()
    assert "post_incident_review_url" in incident_dict
    assert incident_dict["post_incident_review_url"] == (
        "https://map.pgmac.net/incidents/2025-01-10-dbserver01/"
    )


def test_incident_pir_url_nullable(db_session):
    """Test that PIR URL can be None."""
    now = datetime.now()
    incident = Incident(
        incident_type="service",
        host_name="appserver01",
        service_description="API",
        state="WARNING",
        started_at=now,
        ended_at=None,
        post_incident_review_url=None,
    )
    db_session.add(incident)
    db_session.commit()
    db_session.refresh(incident)

    assert incident.post_incident_review_url is None


def test_get_incident_includes_pir_url(client, sample_incident, db_session):
    """Test that GET /api/incidents/{id} includes PIR URL."""
    # Update the incident with a PIR URL
    sample_incident.post_incident_review_url = "https://map.pgmac.net/incidents/2025-01-10-test/"
    db_session.commit()

    response = client.get(f"/api/incidents/{sample_incident.id}")
    assert response.status_code == 200

    data = response.json()
    assert "incident" in data
    assert "post_incident_review_url" in data["incident"]
    assert data["incident"]["post_incident_review_url"] == (
        "https://map.pgmac.net/incidents/2025-01-10-test/"
    )


def test_update_pir_url_success(client, sample_incident, db_session):
    """Test that updating PIR URL requires authentication."""
    pir_url = "https://map.pgmac.net/incidents/2025-01-10-webserver01/"

    response = client.patch(
        f"/api/incidents/{sample_incident.id}/pir",
        json={"post_incident_review_url": pir_url}
    )

    # Should require authentication
    assert response.status_code == 401


def test_update_pir_url_incident_not_found(client):
    """Test that updating PIR URL requires authentication (even for non-existent incident)."""
    response = client.patch(
        "/api/incidents/99999/pir",
        json={"post_incident_review_url": "https://example.com/pir/"}
    )

    # Should require authentication before checking if incident exists
    assert response.status_code == 401


def test_update_pir_url_validation(client, sample_incident):
    """Test that PIR URL validation requires authentication first."""
    # Empty string should fail validation, but auth is checked first
    response = client.patch(
        f"/api/incidents/{sample_incident.id}/pir",
        json={"post_incident_review_url": ""}
    )

    # Should require authentication before validation
    assert response.status_code == 401


def test_update_pir_url_too_long(client, sample_incident):
    """Test that long PIR URL requires authentication first."""
    long_url = "https://example.com/" + "a" * 500

    response = client.patch(
        f"/api/incidents/{sample_incident.id}/pir",
        json={"post_incident_review_url": long_url}
    )

    # Should require authentication before validation
    assert response.status_code == 401


def test_list_incidents_includes_pir_url(client, sample_incident, db_session):
    """Test that GET /api/incidents includes PIR URL."""
    # Update the incident with a PIR URL
    sample_incident.post_incident_review_url = "https://map.pgmac.net/incidents/2025-01-10-test/"
    db_session.commit()

    response = client.get("/api/incidents?hours=24")
    assert response.status_code == 200

    incidents = response.json()
    assert len(incidents) > 0

    # Find our incident
    our_incident = next((inc for inc in incidents if inc["id"] == sample_incident.id), None)
    assert our_incident is not None
    assert our_incident["post_incident_review_url"] == (
        "https://map.pgmac.net/incidents/2025-01-10-test/"
    )


def test_update_pir_url_multiple_times(client, sample_incident, db_session):
    """Test that updating PIR URL multiple times requires authentication."""
    first_url = "https://map.pgmac.net/incidents/2025-01-10-wrong/"

    # First update attempt
    response = client.patch(
        f"/api/incidents/{sample_incident.id}/pir",
        json={"post_incident_review_url": first_url}
    )

    # Should require authentication
    assert response.status_code == 401

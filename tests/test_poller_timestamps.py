"""Integration tests covering the poller's timestamp writes.

The poller is the application's main write path. Every timestamp it persists
must be timezone-aware UTC, or UTCDateTime rejects it -- so a full poll against
a real status.dat fixture is the most direct check that the conversion is
complete.
"""

import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

from nagios_public_status_page.collector.poller import StatusPoller
from nagios_public_status_page.config import Config, DatabaseConfig, NagiosConfig
from nagios_public_status_page.models import Incident, PollMetadata


@pytest.fixture
def poller():
    """Return a poller wired to the sample status.dat and a temporary database.

    ``get_database`` caches a module-level singleton, so it is reset around each
    test; otherwise the poller binds to whichever database a previous test
    created, which may already have been deleted.
    """
    from nagios_public_status_page.db import database as database_module

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    previous_instance = database_module._db_instance
    database_module._db_instance = None

    fixture = Path(__file__).parent / "fixtures" / "sample_status.dat"
    config = Config(
        nagios=NagiosConfig(status_dat_path=str(fixture)),
        database=DatabaseConfig(path=db_path),
    )

    yield StatusPoller(config)

    database_module._db_instance = previous_instance
    Path(db_path).unlink(missing_ok=True)


def _unexpected(errors: list[str]) -> list[str]:
    """Filter out the staleness warning the checked-in fixture always triggers.

    sample_status.dat has a fixed mtime in the repository, so every poll against
    it reports stale data. Any *other* error means a write failed.
    """
    return [e for e in errors if "stale" not in e]


def test_poll_completes_without_errors(poller):
    """A full poll writes successfully, so no naive timestamp was rejected."""
    results = poller.poll()

    assert _unexpected(results["errors"]) == []
    assert isinstance(results["timestamp"], datetime)
    assert results["timestamp"].tzinfo is not None


def test_poll_persists_aware_metadata(poller):
    """Poll metadata round-trips out of storage as aware UTC."""
    poller.poll()

    session = poller._get_session()
    try:
        metadata = session.query(PollMetadata).order_by(PollMetadata.id.desc()).first()

        assert metadata is not None
        assert metadata.last_poll_time.tzinfo is not None
        assert metadata.status_dat_mtime.tzinfo is not None

        # The exact subtraction performed by routes.py and poller.py, which
        # would raise TypeError if either side came back naive.
        age = (datetime.now(UTC) - metadata.status_dat_mtime).total_seconds()
        assert age >= 0
    finally:
        session.close()


def test_poll_persists_aware_incident_timestamps(poller):
    """Incidents created from status.dat carry aware UTC timestamps."""
    poller.poll()

    session = poller._get_session()
    try:
        incidents = session.query(Incident).all()

        assert incidents, "sample_status.dat should produce at least one incident"
        for incident in incidents:
            assert incident.started_at.tzinfo is not None
            if incident.ended_at is not None:
                assert incident.ended_at.tzinfo is not None
            if incident.last_check is not None:
                assert incident.last_check.tzinfo is not None
    finally:
        session.close()


def test_repeated_poll_is_stable(poller):
    """A second poll updates existing incidents without a timestamp error."""
    poller.poll()
    results = poller.poll()

    assert _unexpected(results["errors"]) == []


def test_staleness_check_handles_aware_mtime(poller):
    """Parser staleness arithmetic works against the aware file mtime."""
    poller.parser.parse()

    assert poller.parser.file_mtime.tzinfo is not None
    assert isinstance(poller.parser.get_data_age_seconds(), float)
    assert poller.parser.is_data_stale(threshold_seconds=1) is True

"""Tests that /api/health reports the scheduler that is actually running.

The endpoint used to construct a fresh StatusPoller per request and describe
that object. A new poller has is_running=False, and _get_health_status() returns
"critical" on exactly that, so the endpoint reported a stopped scheduler at all
times regardless of the real one (#60).
"""

import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nagios_public_status_page.api.routes import get_db, get_poller, verify_write_access
from nagios_public_status_page.collector.poller import StatusPoller
from nagios_public_status_page.config import Config, DatabaseConfig, NagiosConfig
from nagios_public_status_page.main import app
from nagios_public_status_page.models import Base

FIXTURE = Path(__file__).parent / "fixtures" / "sample_status.dat"


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
def poller():
    """Build a poller against the sample status.dat and a temporary database."""
    from nagios_public_status_page.db import database as database_module

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    previous = database_module._db_instance
    database_module._db_instance = None

    instance = StatusPoller(
        Config(
            nagios=NagiosConfig(status_dat_path=str(FIXTURE)),
            database=DatabaseConfig(path=db_path),
        )
    )

    yield instance

    if instance.is_running:
        instance.stop()
    database_module._db_instance = previous
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def client(db_engine):
    """Test client with the database overridden and no poller attached."""

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


def _scheduler(client) -> dict:
    """Return the scheduler_status block from a health check."""
    response = client.get("/api/health")
    assert response.status_code == 200
    return response.json()["scheduler_status"]


def test_health_reports_a_running_scheduler_as_running(client, poller):
    """A started poller must be reported as running.

    This is the regression test for #60. Before the fix the endpoint built its
    own poller and reported is_running=False here, whatever the real one was
    doing.
    """
    poller.start()
    # start() runs an immediate poll and the checked-in fixture always reports
    # stale data, so clear the resulting failure to isolate the wiring.
    poller._consecutive_failures = 0
    app.dependency_overrides[get_poller] = lambda: poller

    scheduler = _scheduler(client)

    assert scheduler["is_running"] is True
    assert scheduler["scheduler_running"] is True
    assert scheduler["health_status"] == "healthy"


def test_health_reports_a_stopped_scheduler_as_critical(client, poller):
    """A genuinely stopped poller must still raise the alarm."""
    app.dependency_overrides[get_poller] = lambda: poller

    scheduler = _scheduler(client)

    assert scheduler["is_running"] is False
    assert scheduler["health_status"] == "critical"


def test_health_reports_critical_when_no_poller_is_attached(client):
    """No poller means startup failed, which is critical rather than healthy."""
    app.dependency_overrides[get_poller] = lambda: None

    scheduler = _scheduler(client)

    assert scheduler["is_running"] is False
    assert scheduler["health_status"] == "critical"


def test_health_surfaces_the_real_failure_counter(client, poller):
    """consecutive_failures must come from the running poller, not always zero."""
    poller.start()
    poller._consecutive_failures = 2
    app.dependency_overrides[get_poller] = lambda: poller

    scheduler = _scheduler(client)

    assert scheduler["consecutive_failures"] == 2
    assert scheduler["health_status"] == "degraded"


def test_health_reports_degraded_scheduler_distinctly_from_stopped(client, poller):
    """Degraded and critical must be distinguishable, or the field is useless."""
    poller.start()
    poller._consecutive_failures = poller._max_consecutive_failures
    app.dependency_overrides[get_poller] = lambda: poller

    assert _scheduler(client)["health_status"] == "critical"


def test_manual_poll_updates_the_running_poller(client, poller):
    """POST /api/poll must act on the shared instance, not a throwaway one.

    Previously a manual poll ran against a discarded object, so any failure it
    encountered never reached the self-healing state the scheduler relies on.
    """
    poller.start()
    app.dependency_overrides[get_poller] = lambda: poller
    # /api/poll is a write endpoint; HTTPBasic auto-401s without a header.
    app.dependency_overrides[verify_write_access] = lambda: None

    response = client.post("/api/poll")

    assert response.status_code == 200
    # The sample fixture has a fixed mtime, so the poll reports stale data and
    # writes metadata through the shared poller's own database handle.
    assert poller.get_last_poll() is not None


def test_lifespan_attaches_the_poller_to_app_state(monkeypatch, db_engine):
    """The wiring itself: lifespan must publish the poller on app.state.

    No existing test ran the lifespan handler, which is how the endpoint and the
    real poller drifted apart unnoticed.
    """
    started = {}

    class FakePoller:
        is_running = False

        def start(self):
            started["yes"] = True
            self.is_running = True

        def stop(self):
            self.is_running = False

    monkeypatch.setattr(
        "nagios_public_status_page.main.StatusPoller", lambda config: FakePoller()
    )

    with TestClient(app):
        assert started.get("yes") is True
        assert isinstance(app.state.poller, FakePoller)
        assert app.state.poller.is_running is True

    # Shutdown clears it so a stale instance cannot be reported later.
    assert app.state.poller is None

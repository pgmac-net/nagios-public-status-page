"""Tests that configuration is loaded once per application lifetime, not per request.

Before this fix, every route called load_config() itself, re-reading and
re-parsing config.yaml from disk on each request. verify_write_access -- a
dependency on every write endpoint -- did this on the authentication path
ahead of the credential comparison. Worse, the poller (started once at import
time in main.py) and the routes (reloading every request) could silently
disagree about the running configuration if config.yaml changed underneath a
live container (#67).
"""

import tempfile
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import nagios_public_status_page.config as config_module
from nagios_public_status_page.api.routes import get_config
from nagios_public_status_page.db import database as database_module
from nagios_public_status_page.main import app


@pytest.fixture
def isolated_database(monkeypatch):
    """Point the app at a private temp database and isolate the db singleton.

    get_database() caches a process-wide singleton (see #60), so running a
    real lifespan here -- which constructs a StatusPoller and therefore calls
    get_database() -- would otherwise bind every *other* test in the session
    to whatever database.path this file's config happened to use, even tests
    that carefully override get_db for their own routes. Reset before and
    after, and use a private DATABASE_PATH so nothing here touches the real
    ./data/status.db or any other test's database.

    Initialises the singleton immediately (rather than leaving it None for a
    StatusPoller to lazily create later) because the get_db dependency used
    directly by several routes calls get_session(), which requires the
    singleton to already exist -- unlike get_database(path), it does not
    accept a path and initialise on demand.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    monkeypatch.setenv("DATABASE_PATH", db_path)

    previous = database_module._db_instance
    database_module._db_instance = None
    database_module.get_database(db_path)

    yield db_path

    database_module._db_instance = previous
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def load_config_counter(monkeypatch):
    """Count real load_config() calls and expose the counter."""
    original = config_module.load_config
    calls = {"count": 0}

    def counting_load_config(*args, **kwargs):
        calls["count"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(config_module, "load_config", counting_load_config)
    return calls


def test_config_is_loaded_once_across_many_requests(
    load_config_counter, isolated_database, monkeypatch
):
    """Driving several endpoints through a real lifespan must not reload config.

    This is the regression test for #67 and fails on the pre-fix source: each
    of the four requests below used to call load_config() itself.
    """
    monkeypatch.setenv("NAGIOS_STATUS_DAT_PATH", "/nonexistent/status.dat")

    with TestClient(app) as client:
        # main.py's module-level load_config() ran once, at import time, before
        # this fixture's monkeypatch was even installed -- so the baseline here
        # is whatever the counter was already at when the app came up.
        baseline = load_config_counter["count"]

        client.get("/api/health")
        client.get("/api/status")
        client.get("/api/hosts")
        client.get("/api/services")

        assert load_config_counter["count"] == baseline, (
            "load_config() was called during request handling; configuration "
            "should come from app.state via get_config, not be re-read per request"
        )


def test_routes_and_poller_observe_the_same_configuration(isolated_database, monkeypatch):
    """The value app.state.config exposes must be the exact object main.py loaded.

    Guards against a fix that loads a *second*, independent Config on startup --
    which would stop the per-request re-parsing but still leave two
    configurations that could drift, just both cached instead of one cached and
    one live.
    """
    monkeypatch.setenv("NAGIOS_STATUS_DAT_PATH", "/nonexistent/status.dat")

    with TestClient(app):
        assert app.state.config is not None
        assert app.state.poller.config is app.state.config


def test_get_config_falls_back_when_lifespan_has_not_run(monkeypatch):
    """Without a running lifespan, get_config() must still return something usable.

    Several existing test fixtures use TestClient(app) without a context
    manager, which skips lifespan entirely -- get_poller already has this same
    fallback, for the same reason.
    """
    monkeypatch.setenv("NAGIOS_STATUS_DAT_PATH", "/nonexistent/status.dat")

    # app.state persists across TestClient instances that never ran lifespan
    # (it's a plain object, not reset between clients), so it must be cleared
    # explicitly rather than relying on a fresh app or client to start empty.
    app.state.config = None

    class FakeRequest:
        app = app

    config = get_config(FakeRequest())

    assert config.nagios.status_dat_path == "/nonexistent/status.dat"


def test_write_endpoint_auth_still_works_with_cached_config(isolated_database):
    """verify_write_access must authenticate correctly via the injected config.

    It is a Depends() itself now, nested inside another Depends() -- this
    confirms that resolves, and that basic auth still functions.

    app.state.config is set once from main.py's module-level configuration,
    loaded at import time, so a test cannot influence it with env vars set
    inside the test function -- it overrides the get_config dependency
    directly instead, the same way other tests override get_db and get_poller.
    No lifespan runs here (plain TestClient(app), no `with`), so no
    StatusPoller is started by the app itself -- but /api/poll builds one on
    demand when no poller is attached, which needs a database, hence
    isolated_database rather than relying on some other test having already
    initialised the global singleton.
    """
    configured = config_module.Config(
        nagios=config_module.NagiosConfig(status_dat_path="/nonexistent/status.dat"),
        api=config_module.APIConfig(
            basic_auth_username="admin", basic_auth_password="secret"
        ),
        database=config_module.DatabaseConfig(path=isolated_database),
    )
    app.dependency_overrides[get_config] = lambda: configured

    try:
        client = TestClient(app)

        assert client.post("/api/poll").status_code == 401
        assert client.post(
            "/api/poll", auth=("admin", "wrong-password")
        ).status_code == 401

        response = client.post("/api/poll", auth=("admin", "secret"))
        assert response.status_code in (200, 500)  # 500 = no status.dat file
    finally:
        app.dependency_overrides.pop(get_config, None)

"""Tests that configuration is loaded once per application lifetime, not per request.

Before this fix, every route called load_config() itself, re-reading and
re-parsing config.yaml from disk on each request. verify_write_access -- a
dependency on every write endpoint -- did this on the authentication path
ahead of the credential comparison. Worse, the poller (started once at import
time in main.py) and the routes (reloading every request) could silently
disagree about the running configuration if config.yaml changed underneath a
live container (#67).
"""

import pytest
from starlette.testclient import TestClient

import nagios_public_status_page.config as config_module
from nagios_public_status_page.api.routes import get_config
from nagios_public_status_page.config import APIConfig, Config, NagiosConfig
from nagios_public_status_page.main import app


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


def test_config_is_loaded_once_across_many_requests(load_config_counter, monkeypatch):
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


def test_routes_and_poller_observe_the_same_configuration(monkeypatch):
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


def test_write_endpoint_auth_still_works_with_cached_config():
    """verify_write_access must authenticate correctly via the injected config.

    It is a Depends() itself now, nested inside another Depends() -- this
    confirms that resolves, and that basic auth still functions.

    app.state.config is set once from main.py's module-level configuration,
    loaded at import time, so a test cannot influence it with env vars set
    inside the test function -- it overrides the get_config dependency
    directly instead, the same way other tests override get_db and get_poller.
    """
    configured = Config(
        nagios=NagiosConfig(status_dat_path="/nonexistent/status.dat"),
        api=APIConfig(basic_auth_username="admin", basic_auth_password="secret"),
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

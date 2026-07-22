"""Tests for the /api/graph proxy route."""

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from nagios_public_status_page.api.graph_signing import sign_graph_params
from nagios_public_status_page.api.routes import router
from nagios_public_status_page.config import Config, GraphConfig, NagiosConfig

SECRET = "test-secret"


def make_config(**graph_overrides) -> Config:
    graph_kwargs = {
        "nagiosgraph_url": "http://nagios.int.test/cgi-bin",
        "signing_secret": SECRET,
    }
    graph_kwargs.update(graph_overrides)
    return Config(
        nagios=NagiosConfig(status_dat_path="/dev/null"),
        graph=GraphConfig(**graph_kwargs),
    )


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_graph_returns_503_when_unconfigured(client, monkeypatch):
    monkeypatch.setattr(
        "nagios_public_status_page.config.load_config",
        lambda: make_config(nagiosgraph_url=None, signing_secret=None),
    )

    response = client.get(
        "/api/graph", params={"host": "macro", "service": "plexweb", "period": "day", "expires": 0, "sig": "x"}
    )

    assert response.status_code == 503


def test_graph_returns_400_for_invalid_signature(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    response = client.get(
        "/api/graph",
        params={"host": "macro", "service": "plexweb", "period": "day", "expires": 9999999999, "sig": "bad"},
    )

    assert response.status_code == 400


def _fake_async_client(response):
    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            return response

    return FakeAsyncClient


class _FakeResponse:
    def __init__(self, content, status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        pass


REAL_PNG_BYTES = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRfake-rest-of-file"


def test_graph_proxies_png_on_valid_signature(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    monkeypatch.setattr(
        httpx, "AsyncClient", _fake_async_client(_FakeResponse(REAL_PNG_BYTES))
    )

    response = client.get("/api/graph", params=params)

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == REAL_PNG_BYTES


def test_graph_returns_502_when_upstream_body_is_not_a_png(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    html_body = b"<!DOCTYPE html><html><body>not a graph</body></html>"
    monkeypatch.setattr(
        httpx, "AsyncClient", _fake_async_client(_FakeResponse(html_body))
    )

    response = client.get("/api/graph", params=params)

    assert response.status_code == 502


def test_graph_computes_offset_from_timet_at_request_time(client, monkeypatch):
    """offset must be derived from timet at fetch time, not baked into the
    signed URL — otherwise the window drifts back to "live" the moment the
    URL is re-fetched later than it was signed (e.g. by Slack's image proxy).
    """
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    sign_time = 1_000_000_000
    event_timet = sign_time - 3600
    params = sign_graph_params(
        "macro", "plexweb", "day", SECRET, ttl_seconds=60, timet=event_timet
    )

    captured_params = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, auth=None):
            captured_params.update(params or {})
            return _FakeResponse(REAL_PNG_BYTES)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    # Fetch happens 6 hours after the URL was signed — a stand-in for Slack
    # re-fetching a stale message image well after the alert fired.
    fetch_time = sign_time + 6 * 3600
    monkeypatch.setattr("nagios_public_status_page.api.routes.time.time", lambda: fetch_time)

    response = client.get("/api/graph", params=params)

    assert response.status_code == 200
    # offset is relative to fetch_time, not sign_time, so the window stays
    # anchored to event_timet regardless of when the request lands.
    assert captured_params["offset"] == fetch_time - event_timet


def test_graph_timet_zero_is_live(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60, timet=0)

    captured_params = {}

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, params=None, auth=None):
            captured_params.update(params or {})
            return _FakeResponse(REAL_PNG_BYTES)

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/api/graph", params=params)

    assert response.status_code == 200
    assert captured_params["offset"] == 0


def test_graph_returns_400_when_timet_is_tampered(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60, timet=3600)
    params["timet"] = "0"

    response = client.get("/api/graph", params=params)

    assert response.status_code == 400


def test_graph_returns_502_on_upstream_error(client, monkeypatch):
    monkeypatch.setattr("nagios_public_status_page.config.load_config", make_config)

    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, *args, **kwargs):
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)

    response = client.get("/api/graph", params=params)

    assert response.status_code == 502

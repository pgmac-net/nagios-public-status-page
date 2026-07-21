"""Tests for the signed nagiosgraph proxy URL helpers."""

import time

import pytest

from nagios_public_status_page.api.graph_signing import (
    ALLOWED_PERIODS,
    GraphRequest,
    sign_graph_params,
    verify_graph_signature,
)

SECRET = "test-secret"


def _request_from_params(params: dict[str, str]) -> GraphRequest:
    return GraphRequest(
        host=params["host"],
        service=params["service"],
        period=params["period"],
        offset=int(params["offset"]),
        expires=int(params["expires"]),
    )


def test_sign_and_verify_round_trip():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    assert verify_graph_signature(_request_from_params(params), params["sig"], SECRET)


def test_verify_rejects_wrong_secret():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    assert not verify_graph_signature(_request_from_params(params), params["sig"], "wrong-secret")


def test_verify_rejects_tampered_host():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)
    tampered = _request_from_params(params)
    tampered = GraphRequest(
        host="different-host",
        service=tampered.service,
        period=tampered.period,
        offset=tampered.offset,
        expires=tampered.expires,
    )

    assert not verify_graph_signature(tampered, params["sig"], SECRET)


def test_verify_rejects_tampered_offset():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60, offset=3600)
    tampered = _request_from_params(params)
    tampered = GraphRequest(
        host=tampered.host,
        service=tampered.service,
        period=tampered.period,
        offset=0,
        expires=tampered.expires,
    )

    assert not verify_graph_signature(tampered, params["sig"], SECRET)


def test_verify_rejects_expired_signature():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=-1)

    assert not verify_graph_signature(_request_from_params(params), params["sig"], SECRET)


def test_verify_rejects_disallowed_period():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)
    request = _request_from_params(params)
    request = GraphRequest(
        host=request.host,
        service=request.service,
        period="not-a-real-period",
        offset=request.offset,
        expires=request.expires,
    )

    assert not verify_graph_signature(request, params["sig"], SECRET)


def test_sign_rejects_disallowed_period():
    with pytest.raises(ValueError):
        sign_graph_params("macro", "plexweb", "not-a-real-period", SECRET, ttl_seconds=60)


def test_expires_is_in_the_future_for_positive_ttl():
    params = sign_graph_params("macro", "plexweb", "week", SECRET, ttl_seconds=3600)

    assert int(params["expires"]) > time.time()


def test_offset_defaults_to_zero():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60)

    assert params["offset"] == "0"


def test_sign_and_verify_round_trip_with_offset():
    params = sign_graph_params("macro", "plexweb", "day", SECRET, ttl_seconds=60, offset=3600)

    assert params["offset"] == "3600"
    assert verify_graph_signature(_request_from_params(params), params["sig"], SECRET)


def test_all_allowed_periods_sign_successfully():
    for period in ALLOWED_PERIODS:
        params = sign_graph_params("macro", "plexweb", period, SECRET, ttl_seconds=60)
        assert params["period"] == period

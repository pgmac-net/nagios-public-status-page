"""HMAC signing/verification for public nagiosgraph proxy URLs.

Slack cannot reach the internal, Access-protected Nagios instance to render
inline graph images. This module lets us hand out short-lived, signed URLs
for a narrow, whitelisted set of (host, service, period) combinations so the
public proxy endpoint never becomes an open pass-through to the nagiosgraph
CGI.
"""

import hashlib
import hmac
import time
from dataclasses import dataclass

ALLOWED_PERIODS = frozenset({"day", "week", "month", "quarter", "year"})


@dataclass(frozen=True)
class GraphRequest:
    """The signed fields of a graph proxy request."""

    host: str
    service: str
    period: str
    timet: int
    expires: int

    def payload(self) -> bytes:
        """Canonical byte payload that gets HMAC-signed."""
        return f"{self.host}|{self.service}|{self.period}|{self.timet}|{self.expires}".encode()


def sign_graph_params(
    host: str, service: str, period: str, secret: str, ttl_seconds: int, timet: int = 0
) -> dict[str, str]:
    """Build signed, expiring query params for the graph proxy endpoint.

    Args:
        host: Nagios host name.
        service: Nagios service description.
        period: Graph period; must be one of ALLOWED_PERIODS.
        secret: Shared HMAC signing secret.
        ttl_seconds: Seconds until the signature expires.
        timet: Absolute unix epoch of the event to anchor the graph window
            to — 0 means live (window ends now). Anchoring to an absolute
            time, rather than a relative offset computed once at sign time,
            keeps the window fixed at the alert's own time regardless of
            when the image is later re-fetched (e.g. by Slack's image proxy).

    Returns:
        Query params (host, service, period, timet, expires, sig) for /api/graph.

    Raises:
        ValueError: If period is not in ALLOWED_PERIODS.
    """
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period must be one of {sorted(ALLOWED_PERIODS)}, got {period!r}")

    expires = int(time.time()) + ttl_seconds
    request = GraphRequest(host=host, service=service, period=period, timet=timet, expires=expires)
    sig = hmac.new(secret.encode("utf-8"), request.payload(), hashlib.sha256).hexdigest()

    return {
        "host": host,
        "service": service,
        "period": period,
        "timet": str(timet),
        "expires": str(expires),
        "sig": sig,
    }


def verify_graph_signature(request: GraphRequest, sig: str, secret: str) -> bool:
    """Verify a graph proxy request's signature and expiry.

    Args:
        request: The signed fields (host, service, period, expires) from the request.
        sig: Signature supplied in the request.
        secret: Shared HMAC signing secret.

    Returns:
        True if the signature is valid and not expired.
    """
    if request.period not in ALLOWED_PERIODS:
        return False

    if time.time() > request.expires:
        return False

    expected_sig = hmac.new(secret.encode("utf-8"), request.payload(), hashlib.sha256).hexdigest()

    return hmac.compare_digest(expected_sig, sig)

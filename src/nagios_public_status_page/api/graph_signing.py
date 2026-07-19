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
    expires: int

    def payload(self) -> bytes:
        """Canonical byte payload that gets HMAC-signed."""
        return f"{self.host}|{self.service}|{self.period}|{self.expires}".encode("utf-8")


def sign_graph_params(
    host: str, service: str, period: str, secret: str, ttl_seconds: int
) -> dict[str, str]:
    """Build signed, expiring query params for the graph proxy endpoint.

    Args:
        host: Nagios host name.
        service: Nagios service description.
        period: Graph period; must be one of ALLOWED_PERIODS.
        secret: Shared HMAC signing secret.
        ttl_seconds: Seconds until the signature expires.

    Returns:
        Query params (host, service, period, expires, sig) for /api/graph.

    Raises:
        ValueError: If period is not in ALLOWED_PERIODS.
    """
    if period not in ALLOWED_PERIODS:
        raise ValueError(f"period must be one of {sorted(ALLOWED_PERIODS)}, got {period!r}")

    expires = int(time.time()) + ttl_seconds
    request = GraphRequest(host=host, service=service, period=period, expires=expires)
    sig = hmac.new(secret.encode("utf-8"), request.payload(), hashlib.sha256).hexdigest()

    return {
        "host": host,
        "service": service,
        "period": period,
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

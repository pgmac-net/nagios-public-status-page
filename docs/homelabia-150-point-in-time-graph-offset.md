# homelabia#150: Point-in-time Nagiosgraph Offset

## Summary

`/api/graph` now accepts a signed `offset` query param that shifts the nagiosgraph window backward from now, so the graph proxy can render a point-in-time snapshot instead of always the live graph. `offset` is part of the HMAC-SHA256 payload, so a captured signed URL can't be replayed with a different window.

PR: [https://github.com/pgmac-net/nagios-public-status-page/pull/52](https://github.com/pgmac-net/nagios-public-status-page/pull/52)
Companion PR (Slack script): [https://github.com/pgmac-net/nagios-config/pull/27](https://github.com/pgmac-net/nagios-config/pull/27)
Ticket: [https://github.com/pgmac-net/homelabia/issues/150](https://github.com/pgmac-net/homelabia/issues/150)

## Why

The graph embedded in Slack notifications (homelabia#148) always rendered live. A historical Slack message — viewed after the fact, or once the metric recovered — still showed "now" instead of what the metric looked like at alert time. nagiosgraph's `showgraph.cgi` already supports an `offset=<seconds>` CGI param that shifts the graph window backward, so the fix was to thread that through the existing signed-URL chain rather than building anything new.

## Endpoint

```
GET /api/graph?host=<host>&service=<service>&period=<period>&offset=<seconds>&expires=<unix-ts>&sig=<hex>
```

- `offset` — seconds to shift the window backward from now. `0` (default) = live, unchanged from before.
- `sig` = `HMAC-SHA256(secret, "{host}|{service}|{period}|{offset}|{expires}")`, hex-encoded — the payload shape changed to include `offset`.
- Everything else (period whitelist, 400/503/502 semantics, PNG magic-byte check) is unchanged from homelabia#148.

## Generating a signed URL

```python
from nagios_public_status_page.api.graph_signing import sign_graph_params

params = sign_graph_params("web01", "HTTPS", "day", secret, ttl_seconds=604800, offset=3600)
```

`offset` defaults to `0` if omitted — existing callers that don't pass it keep today's live-graph behaviour.

## Testing

- `uv run pytest` — 69 passed (7 new: offset round-trip, offset default, tampered-offset rejection, offset forwarded to upstream CGI call)
- `uv run ruff check` on touched files — clean
- `uv run pylint` — no new violations beyond the pre-existing class already present on `get_graph` (repo has no pylint CI gate; baseline score 5.71/10 unaffected in kind)
- Cross-checked bash (`openssl dgst -sha256 -hmac`) vs Python (`sign_graph_params`) signature generation with a nonzero offset — identical output

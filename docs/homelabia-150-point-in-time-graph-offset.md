# homelabia#150: Point-in-time Nagiosgraph Offset

## Summary

`/api/graph` accepts a signed `timet` query param — an absolute unix epoch — that anchors the nagiosgraph window to a fixed point in time instead of always rendering live. On every request the proxy computes `offset = max(0, now - timet)` and forwards it to nagiosgraph, so the window stays anchored to `timet` no matter when the URL is actually fetched. `timet` is part of the HMAC-SHA256 payload, so a captured signed URL can't be replayed with a different anchor.

PR: [https://github.com/pgmac-net/nagios-public-status-page/pull/52](https://github.com/pgmac-net/nagios-public-status-page/pull/52) (superseded by the `timet` follow-up PR)
Companion PR (Slack script): [https://github.com/pgmac-net/nagios-config/pull/27](https://github.com/pgmac-net/nagios-config/pull/27) (superseded)
Ticket: [https://github.com/pgmac-net/homelabia/issues/150](https://github.com/pgmac-net/homelabia/issues/150)

## Why

The graph embedded in Slack notifications (homelabia#148) always rendered live. A historical Slack message — viewed after the fact, or once the metric recovered — still showed "now" instead of what the metric looked like at alert time. nagiosgraph's `showgraph.cgi` already supports an `offset=<seconds>` CGI param that shifts the graph window backward, so the natural first attempt was to thread a relative offset through the existing signed-URL chain.

That first attempt (`offset` in the signed payload, computed once at notification time) shipped but didn't fix the problem, for two compounding reasons:

1. Nagios's `$TIMET$` macro is "now" at notification send time, not the event time — so the computed offset was always ≈0.
2. Even with a correct event time, a relative offset baked into the signed URL is interpreted relative to *whenever the URL is fetched*. Slack's image proxy re-fetches the URL on its own schedule, sometimes well after signing, so a fixed offset drifts back toward "live" with every re-fetch.

The fix: sign an **absolute anchor epoch** (`timet`) instead of a relative offset, and have the proxy compute the actual `offset` to send to nagiosgraph fresh on every request, relative to that fixed anchor. The window is now genuinely pinned to the alert's own time regardless of when Slack (or anything else) fetches the image.

## Endpoint

```
GET /api/graph?host=<host>&service=<service>&period=<period>&timet=<unix-ts>&expires=<unix-ts>&sig=<hex>
```

- `timet` — absolute unix epoch to anchor the graph window to. `0` (default) = live, unchanged from before.
- `sig` = `HMAC-SHA256(secret, "{host}|{service}|{period}|{timet}|{expires}")`, hex-encoded.
- Everything else (period whitelist, 400/503/502 semantics, PNG magic-byte check) is unchanged from homelabia#148.

On the `nagios-config` side, `notify_slack.sh` now signs `$LASTSERVICESTATECHANGE$` / `$LASTHOSTSTATECHANGE$` (the actual state-transition epoch) as `timet`, rather than `$TIMET$` (which is always "now").

## Generating a signed URL

```python
from nagios_public_status_page.api.graph_signing import sign_graph_params

params = sign_graph_params("web01", "HTTPS", "day", secret, ttl_seconds=604800, timet=1721600000)
```

`timet` defaults to `0` if omitted — existing callers that don't pass it keep today's live-graph behaviour.

## Testing

- `uv run pytest` — 70 passed, including a frozen-clock test proving the offset sent upstream is recomputed at fetch time (not sign time) and still anchors correctly to `timet` hours after signing
- `uv run ruff check` on touched files — clean
- `uv run pylint` — no new violations; score improved slightly vs. the pre-fix baseline
- Cross-checked bash (`openssl dgst -sha256 -hmac`) vs Python (`sign_graph_params`) signature generation with a nonzero `timet` — identical output
- Manually verified against the live proxy: `timet=0` vs `timet=<6h ago>` return visibly different graphs, and `showgraph.cgi?offset=21600` confirmed nagiosgraph honours the offset param in this deployment

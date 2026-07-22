# Signed nagiosgraph proxy (`/api/graph`)

## Purpose

External services (Slack notifications, homelabia#148) need to render a nagiosgraph PNG inline, but the internal Nagios instance (`status.pgmac.net.au`) sits behind Cloudflare Access — external image fetchers can't authenticate through it.

`/api/graph` proxies the internal nagiosgraph CGI from this app's own public host (`statuspage.pgmac.net.au`), which has no Access gate. To avoid becoming an open proxy, requests must carry a valid HMAC-SHA256 signature and only four parameters are ever forwarded upstream.

## Endpoint

```
GET /api/graph?host=<host>&service=<service>&period=<period>&timet=<unix-ts>&expires=<unix-ts>&sig=<hex>
```

- `period` must be one of `day`, `week`, `month`, `quarter`, `year` — anything else is rejected before the signature is even checked.
- `timet` anchors the graph window to an absolute unix epoch — `0` (the default) means live. On every request the endpoint computes `offset = max(0, now - timet)` and forwards that to nagiosgraph's own `offset` CGI param, so the window stays fixed at `timet` regardless of when the URL is actually fetched (homelabia#150). This matters because callers like Slack's image proxy re-fetch the URL on an unpredictable schedule, potentially days after it was signed — a relative offset computed once at sign time would drift back toward "live" with every re-fetch, whereas an absolute anchor doesn't. `timet` is part of the signed payload, so a captured URL can't be replayed with a different anchor.
- `sig` = `HMAC-SHA256(secret, "{host}|{service}|{period}|{timet}|{expires}")`, hex-encoded.
- Requests with an invalid signature or a past `expires` get `400`.
- If `graph.nagiosgraph_url` or `graph.signing_secret` aren't configured, the endpoint returns `503`.
- On success, streams the upstream PNG through with `Content-Type: image/png`.

## Configuration

`config.yaml`:

```yaml
graph:
  nagiosgraph_url: "http://nagios.int.pgmac.net/cgi-bin"
  signing_secret: "change-me"
  default_ttl_seconds: 604800  # 7 days
  basic_auth_username: null
  basic_auth_password: null
```

Or via environment variables (override config.yaml): `GRAPH_NAGIOSGRAPH_URL`, `GRAPH_SIGNING_SECRET`, `GRAPH_DEFAULT_TTL_SECONDS`, `GRAPH_BASIC_AUTH_USERNAME`, `GRAPH_BASIC_AUTH_PASSWORD`.

`signing_secret` must match the `GRAPH_SIGNING_SECRET` used by whatever is generating signed URLs — currently `notify_slack.sh` in [`pgmac-net/nagios-config`](https://github.com/pgmac-net/nagios-config).

## Generating a signed URL

Python (see `src/nagios_public_status_page/api/graph_signing.py`):

```python
from nagios_public_status_page.api.graph_signing import sign_graph_params

params = sign_graph_params("web01", "HTTPS", "day", secret, ttl_seconds=604800, timet=1721600000)
# {"host": ..., "service": ..., "period": ..., "timet": ..., "expires": ..., "sig": ...}
```

`timet` defaults to `0` (live graph) if omitted.

Bash (as used by `notify_slack.sh`):

```bash
expires=$(( $(date +%s) + 604800 ))
payload="${host}|${service}|${period}|${timet}|${expires}"
sig=$(printf '%s' "${payload}" | openssl dgst -sha256 -hmac "${secret}" | awk '{print $NF}')
```

Both produce interoperable signatures — verified in `tests/test_graph_route.py` and cross-checked manually against the bash implementation during homelabia#148.

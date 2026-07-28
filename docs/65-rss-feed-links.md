# #65: RSS feed links pointed at 404s

- **Issue**: [pgmac-net/nagios-public-status-page#65](https://github.com/pgmac-net/nagios-public-status-page/issues/65)
- **PR**: [#68](https://github.com/pgmac-net/nagios-public-status-page/pull/68)
- **Date**: 2026-07-28

## Summary

The RSS feed's channel `<link>` and self-referencing `atom:link` both
advertised `/feed.rss`, which has never been a route. Every entry also linked
to a per-incident page that does not exist. All three are fixed to point at
URLs that actually resolve.

## How it was found

While verifying the deployment during the #60 investigation:

```xml
<link>https://statuspage.pgmac.net.au/feed.rss</link>
<atom:link href="https://statuspage.pgmac.net.au/feed.rss" rel="self"/>
```

```
GET /feed.rss      -> 404
GET /feed/rss.xml  -> 200
```

The router is mounted at `/feed` with a `/rss.xml` route, giving `/feed/rss.xml`
— `/feed.rss` has never existed. A reader subscribing via the self link gets a
404.

## Scope was wider than reported

`_create_base_feed` is shared by all three feed generators (global, host,
service), and the hardcoded `/feed.rss` was passed to every one of them. So the
host and service feeds also advertised the *global* feed's URL, not their own.

A third dead link, not in the original ticket: every entry linked to
`/incidents/{id}`. That also 404s — the frontend has no deep-linking at all, no
hash routing, no `pushState`, no `hashchange` listener, so there is no
per-incident page for an entry to point at.

## Why the obvious fix didn't work

The first attempt set `rel="alternate"` on the status-page link and
`rel="self"` on the feed link, expecting RSS 2.0's `<link>` to come from the
alternate one. It didn't — `feedgen` ignores `rel` entirely for that element and
takes the href of whichever `link()` call happened *last*:

```python
# feedgen/feed.py
if len(self.__atom_link) > 0:
    self.__rss_link = self.__atom_link[-1]["href"]
```

Verified directly against the library:

```
call order [self, alternate] -> <link> = alternate href   (correct)
call order [alternate, self] -> <link> = self href         (the bug)
```

The fix is call order, not the `rel` argument. Both calls still populate the
`atom:link` list correctly regardless of order, so `atom:link rel="self"`
renders correctly either way — only the plain `<link>` element is order-
sensitive.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Channel `<link>` | `config.rss.link` (the status page) | Per the RSS 2.0 spec: "the URL to the HTML website corresponding to the channel" |
| `atom:link rel="self"` | Each feed's real, own path | Global, host and service feeds now advertise distinct, resolvable URLs |
| Entry `<link>` | Status page root | No per-incident page exists to link to |
| Entry `<guid>` | **Unchanged** | See below |
| New config setting | None | `rss.link` already is the site root |

### Why the entry GUID stays as it is

It renders as `<guid isPermaLink="false">`, so per the RSS spec it does not need
to resolve — only to be stable and unique. Changing it would make every
existing item look brand new to subscribers and re-fire notifications for
incidents they've already seen. Left as `/incidents/{id}` even though that URL
404s, because as a non-resolving identifier that is correct behaviour, not a
bug.

### Percent-encoding

Host and service names are percent-encoded when building self-link paths, since
real Nagios service descriptions contain spaces and commas:

```
'Disk Space, /var'  ->  Disk%20Space%2C%20%2Fvar
```

## Testing

The existing RSS tests checked `pubDate` and required fields but never that a
link resolves — which is exactly how this went unnoticed. 8 new tests fetch
each feed's advertised self-link through the **real app via `TestClient`**.

That distinction mattered during implementation: a first attempt reimplemented
FastAPI's route matching by walking `app.routes` by hand, and it silently
*passed* against the still-broken code. FastAPI 0.140 flattens `include_router`
lazily into internal `_IncludedRouter` wrapper objects rather than plain
`APIRoute` objects, so a hand-rolled route walk never sees routes registered
that way. Switched to issuing real requests through the ASGI app instead, which
caught the bug immediately.

6 of 8 relevant tests fail cleanly against unfixed `main`:

```
FAILED test_global_feed_self_link_resolves          .../feed.rss != .../feed/rss.xml
FAILED test_host_feed_self_link_resolves...          .../feed.rss != .../feed/host/macro/rss.xml
FAILED test_service_feed_self_link_resolves...       .../feed.rss != .../feed/service/macro/HTTP/rss.xml
FAILED test_service_feed_self_link_encodes...         .../feed.rss != .../Disk%20Space...
FAILED test_channel_link_is_the_status_page...        <link> held the feed URL, not the site
FAILED test_entry_link_resolves_to_the_status_page    entry linked to /incidents/1
```

Live-shaped render, matching the deployed configuration:

```xml
<link>https://statuspage.pgmac.net.au</link>
<atom:link href="https://statuspage.pgmac.net.au/feed/rss.xml" rel="self"/>
```

```
ruff check src/ tests/ scripts/  ->  All checks passed!
pytest -q                        ->  115 passed  (was 107)
pylint src/...                   ->  7.85/10
```

## Deviations from plan

- Implemented on Sonnet, matching the STANDARD tier as planned.
- The plan didn't anticipate `feedgen`'s call-order behaviour — that required
  reading the library source mid-implementation once the `rel`-based approach
  demonstrably failed its own tests.
- The plan's test approach (walking `app.routes`) had to be replaced entirely
  after it produced false-positive passes against broken code. Not a deviation
  in scope, but worth recording: the first version of the regression tests
  would not have caught the bug they were written for.

## Follow-up

[#69](https://github.com/pgmac-net/nagios-public-status-page/issues/69) — the
service feed route embeds `service_description` as a path segment, which cannot
match a description containing a forward slash at all (`"CPU / Load"`,
`"Disk Space, /var"`), independent of encoding. Pre-existing route design
limitation, found while fixing the self-link generation for exactly this kind
of description. Likely fix is a query parameter, which changes the feed URL
contract and so needs its own ticket.

## Lessons

- **A test that passes against broken code is worse than no test.** The first
  route-matching approach gave false confidence; only running the intended
  suite against the pre-fix source caught that it proved nothing.
- **Don't trust a library's declared API surface (`rel=`) over its actual
  behaviour.** Reading `feedgen`'s source was necessary once the documented
  parameter didn't produce the documented result.
- **Fixing a reported bug can surface adjacent bugs of the same shape.** The
  entry link and the service-route slash limitation were both found by
  generalizing "does this link resolve?" past the two links the ticket named.

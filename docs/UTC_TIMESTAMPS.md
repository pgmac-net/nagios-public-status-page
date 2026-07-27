# UTC Timestamps

Every timestamp in this application is UTC. This document records what that
means at each layer, and why the boundaries are drawn where they are.

## The invariant

| Layer | Representation |
|---|---|
| Python (application code) | timezone-aware, `tzinfo=UTC` |
| SQLite storage | naive string, `YYYY-MM-DD HH:MM:SS.ffffff`, holding the UTC wall clock |
| JSON API responses | naive ISO 8601 string, no offset, interpreted as UTC by clients |
| RSS feed | offset-bearing, rendered by feedgen from the aware value |
| Browser display | converted to the viewer's local timezone by `static/js/app.js` |

## Why storage is naive

SQLite has no native timezone support. SQLAlchemy's SQLite dialect serialises a
datetime to a string with no offset and returns a naive value on read, so
`DateTime(timezone=True)` does nothing on this backend. Worse, it does not
convert: an aware value in a non-UTC zone is stored as its *local* wall clock.

```
column DateTime(timezone=True), value 2026-07-27T22:00:00+10:00
  -> stored as '2026-07-27 22:00:00.000000'
```

That value is really 12:00 UTC, so it now sorts after a genuine 13:00 UTC row.
Adding `timezone=True` would have created that hazard without fixing anything.

## How the invariant is enforced

`nagios_public_status_page.db.types.UTCDateTime` is a `TypeDecorator` applied to
every timestamp column in `models.py`:

- **On write**, it converts an aware value to UTC and strips the tzinfo. A
  *naive* value is rejected with `ValueError`, because a naive datetime carries
  no evidence of its zone and accepting one means guessing.
- **On read**, it attaches `tzinfo=UTC`.

The rejection is the point. A call site that forgets `UTC` fails loudly at write
time instead of silently storing local time that is indistinguishable from UTC
once written.

Ruff's `DTZ005` and `DTZ006` rules are enabled to catch the static cases:
`datetime.now()` and `datetime.fromtimestamp()` without a `tz` argument. Use
`datetime.now(UTC)` and `datetime.fromtimestamp(ts, UTC)`.

## Why the API stays naive

The JSON API has always served timestamps without an offset, and
`static/js/app.js` depends on that shape — `parseUTCDate()` appends `'Z'` to any
value containing `'T'` that does not already end in `'Z'`. An offset-bearing
payload would become `'...+00:00Z'` and parse as `Invalid Date`.

`api/schemas.py` therefore defines a `UTCTimestamp` annotated type that strips
tzinfo at serialisation. Values are aware in Python and naive on the wire, so
the contract is unchanged for the frontend, RSS consumers, and the Slack graph
pipeline.

`Incident.to_dict()` and friends use the same convention via
`models._naive_isoformat()`.

**If you ever change the API to emit offsets, `parseUTCDate()` must change in
the same commit.**

## Container timezone

`Dockerfile` and `docker-compose.yml` both pin `TZ=UTC`.

This is defence in depth, not a dependency. Before this work the application had
no explicit UTC handling at all and was correct *only* because
`python:3.14-slim` defaults to UTC and nothing set `TZ`. Setting
`TZ=Australia/Brisbane` would have silently shifted every stored timestamp, RSS
pubDate, and displayed time by ten hours. The code no longer cares what `TZ`
says, but pinning it keeps container logs and shells consistent with the data.

## Verifying stored data

`scripts/verify_timestamp_utc.py` is a read-only check that reports whether
existing rows look like UTC:

```bash
python scripts/verify_timestamp_utc.py data/status.db
```

It compares the newest `poll_metadata.last_poll_time` against the current UTC
time. A healthy database polls every few minutes, so the gap should be small; a
gap close to a whole number of hours suggests rows written in a non-UTC zone.
The script only issues `SELECT` statements.

No data migration shipped with this change, because the deployed container has
only ever run UTC and the storage format is byte-identical before and after.

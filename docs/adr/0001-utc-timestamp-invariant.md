# 1. UTC timestamp invariant

- **Status**: Accepted
- **Date**: 2026-07-27
- **Issue**: [#56](https://github.com/pgmac-net/nagios-public-status-page/issues/56)
- **PR**: [#58](https://github.com/pgmac-net/nagios-public-status-page/pull/58)

## Context

The application stored and compared naive datetimes throughout. Every
`datetime.now()` and `datetime.fromtimestamp()` call took whatever timezone the
host happened to be configured with, and the SQLAlchemy columns were plain
`DateTime`.

In production this was correct — but only incidentally. `python:3.14-slim`
defaults to UTC, and neither the Dockerfile nor `docker-compose.yml` set `TZ` or
mounted `/etc/localtime`. So inside the container `datetime.now()` returned UTC,
which in turn made the RSS feed's `.replace(tzinfo=UTC)` and the frontend's
`parseUTCDate()` correct too.

Nothing declared or enforced that. Adding `-e TZ=Australia/Brisbane` would have
shifted every stored timestamp, RSS `pubDate` and displayed time by ten hours,
silently and with no error. Development machines already diverged, since they run
local time, so tests and local runs exercised different semantics than
production.

Two further constraints shaped the decision:

**SQLite cannot store an offset.** SQLAlchemy's SQLite dialect serialises a
datetime to a string with no offset and returns a naive value on read, so
`DateTime(timezone=True)` is inert on this backend. It also does not convert:

```
column DateTime(timezone=True), value 2026-07-27T22:00:00+10:00
  -> stored as '2026-07-27 22:00:00.000000'
```

That value is really 12:00 UTC, so it now sorts after a genuine 13:00 UTC row.

**The JSON API contract was already relied upon.** `static/js/app.js`
`parseUTCDate()` appends `'Z'` to any value containing `'T'` that does not
already end in `'Z'`. An offset-bearing payload would become `'...+00:00Z'` and
parse as `Invalid Date`. The RSS feed and the Slack graph pipeline consume the
same API.

## Decision

Timestamps are timezone-aware UTC in Python and naive UTC in storage, enforced
at the database boundary by a `UTCDateTime` `TypeDecorator` applied to every
timestamp column.

- **On write** it converts an aware value to UTC and strips the tzinfo. A naive
  value is **rejected** with `ValueError`.
- **On read** it attaches `tzinfo=UTC`.

The JSON API contract is unchanged. A `UTCTimestamp` annotated type in
`api/schemas.py` strips tzinfo at serialisation, so responses remain
byte-identical to before.

`DTZ005` and `DTZ006` are enabled in ruff. `TZ=UTC` is pinned in the Dockerfile
and compose file as defence in depth, not as a dependency.

### Why naive values are rejected rather than coerced

This is the crux of the design. Coercing a naive value to UTC means guessing
which zone it came from, and a wrong guess writes local time that is
indistinguishable from UTC once stored — the exact failure this ADR exists to
prevent, reintroduced at the one place positioned to catch it.

Rejecting turns a missed call site into an immediate, loud failure at write time.
That guarantee is what allows the rest of the codebase to assume every value
read from the database is aware, which in turn makes every datetime comparison
safe by construction rather than by review.

The trade-off is that any new write path must pass an aware value or fail. That
is the intended cost.

## Consequences

**Positive**

- Correctness no longer depends on ambient `TZ`. The container timezone can
  change without altering behaviour.
- Mixed aware/naive `TypeError` at comparison sites is structurally impossible,
  since database reads are always aware.
- A non-UTC aware value is normalised rather than stored as a wall clock, which
  is what `DateTime(timezone=True)` is commonly mistaken for doing.
- Ruff catches the static cases; the `TypeDecorator` catches the rest at runtime.

**Negative**

- Fixtures and any code writing timestamps must construct aware values.
  Converting the existing tests surfaced this immediately — seven failed until
  updated, which is the mechanism working as designed.
- Values are aware in Python but naive on the wire, so the two representations
  differ. `docs/UTC_TIMESTAMPS.md` documents the boundary.
- The `parseUTCDate()` coupling remains. It is now commented on both sides, but
  a future change to emit offsets must update the frontend in the same commit.

**Neutral**

- No data migration was required. The storage format is byte-identical before
  and after, and verification against the live database on macro.int confirmed
  stored rows were already UTC: a 213s lag against a 300s poll interval, where
  local-time rows would have shown roughly ten hours.

## Alternatives considered

**Add `timezone=True` to the columns.** The original proposal in #56. Rejected:
inert on SQLite, and it introduces the wall-clock corruption described above
without providing the conversion it appears to promise.

**Helper functions and manual normalisation.** A `timeutil` module with
`utc_now()`, `from_epoch()` and `as_utc()`. Smaller diff and no model changes,
but every site mixing a database value with a fresh one must remember to call
`as_utc()`. A missed one is a runtime `TypeError` that no linter can catch.
Rejected for relying on discipline where the `TypeDecorator` relies on structure.

**Full tz-aware end to end, including the API.** Most rigorous, and would let
`parseUTCDate()` be deleted. Rejected as disproportionate: it changes the
contract for every consumer — frontend, RSS readers, Slack graph pipeline — for
no behavioural gain in the UI, since the browser converts to local time either
way.

**Pin `TZ=UTC` and document it, changing nothing else.** Minimal diff. Rejected
because it leaves correctness dependent on deployment configuration rather than
on the code, keeps the ruff ignores, and leaves local development diverging from
production.

## References

- `docs/UTC_TIMESTAMPS.md` — the reference documentation for this invariant
- `src/nagios_public_status_page/db/types.py` — the `UTCDateTime` implementation
- `scripts/verify_timestamp_utc.py` — read-only check that stored rows are UTC

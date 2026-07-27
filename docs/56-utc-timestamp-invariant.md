# #56: UTC Timestamp Invariant

- **Issue**: [pgmac-net/nagios-public-status-page#56](https://github.com/pgmac-net/nagios-public-status-page/issues/56)
- **PR**: [#58](https://github.com/pgmac-net/nagios-public-status-page/pull/58)
- **Reference docs**: [UTC_TIMESTAMPS.md](UTC_TIMESTAMPS.md)
- **Date**: 2026-07-27

## Summary

The application stored and compared naive datetimes end to end. It was correct in
production — but only by accident. This work made the UTC invariant explicit and
enforced, so correctness no longer depends on an undeclared ambient default.

## Origin

This ticket came out of [#55](https://github.com/pgmac-net/nagios-public-status-page/issues/55),
where ruff 0.16.0's expanded default rule set flagged 24 `DTZ005`/`DTZ006`
violations. Those were ignored at the time rather than fixed, because converting
them is a behaviour change, not a lint fix. #56 was raised to do it properly.

## What grilling changed

The original ticket had five scope items. Two were wrong, and investigation
reframed the problem.

### `DateTime(timezone=True)` is a no-op on SQLite

The ticket proposed adding `timezone=True` to the columns. Verified empirically
that this achieves nothing on SQLite, and is actively harmful:

```
column DateTime(timezone=True), value 2026-07-27T12:00:00+00:00
  -> RAW stored: '2026-07-27 12:00:00.000000'   (no offset)
  -> roundtrip:  datetime(2026, 7, 27, 12, 0)   (tzinfo=None)

same column, value 2026-07-27T22:00:00+10:00
  -> RAW stored: '2026-07-27 22:00:00.000000'   (wall clock, NOT converted)
```

SQLAlchemy's SQLite dialect strips tzinfo and does not convert. A `+10:00` value
is stored as its local wall clock, so it sorts after a genuine 13:00 UTC row.
Adding `timezone=True` would have created that hazard without fixing anything.

### Production was already correct, by accident

`python:3.14-slim` defaults to UTC, and neither the Dockerfile nor
`docker-compose.yml` set `TZ` or mounted `/etc/localtime`. So inside the
container `datetime.now()` *is* UTC, which made the RSS `.replace(tzinfo=UTC)`
and the frontend's `parseUTCDate()` correct too.

This reframed the whole ticket. The risk was never wrong data today — it was
that **correctness rested on an ambient default nobody had declared**. Setting
`TZ=Australia/Brisbane` would silently shift every stored timestamp, RSS pubDate
and displayed time by ten hours, with no error anywhere. Dev machines already
diverged, since they run local time.

### No data migration needed

Since the container has only ever run UTC and the storage format is
byte-identical before and after, existing rows are already correct. The ticket's
proposed migration was dropped in favour of a read-only verification script.
Also discovered `migrations/` is not Alembic as the ticket assumed — it is
hand-rolled `sqlite3` scripts.

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Goal | Make UTC explicit in code | Correctness stops depending on ambient `TZ` |
| Data migration | None; ship a read-only verifier | Storage format unchanged, container always UTC |
| JSON API contract | Unchanged — keep naive strings | Frontend, RSS and Slack pipeline all depend on it |
| DB boundary | `UTCDateTime` `TypeDecorator` | Naive values cannot leak out of the DB |

### Why the API contract could not change

Load-bearing detail. `static/js/app.js` `parseUTCDate()` appends `'Z'` to any
value containing `'T'` that does not already end in `'Z'`. An offset-bearing
payload would become `'...+00:00Z'` and parse as `Invalid Date`. Keeping output
byte-identical avoided touching the frontend, RSS consumers, and the Slack graph
pipeline.

Verified before committing to the design:

```
OLD naive -> {"ts":"2026-07-27T12:00:00"}
NEW aware -> {"ts":"2026-07-27T12:00:00"}
match: True
```

### Why naive values are rejected rather than coerced

The `TypeDecorator` raises `ValueError` on a naive write instead of assuming
UTC. A naive datetime carries no evidence of which zone it came from, so
accepting one means guessing — and a wrong guess stores local time that is
indistinguishable from UTC once written. Failing loudly turns a missed call site
into an immediate error rather than silent corruption.

This is the enforcement mechanism the whole design rests on.

## Implementation

- **`db/types.py`** (new) — `UTCDateTime` `TypeDecorator`. Attaches `tzinfo=UTC`
  on read, normalises and strips on write, rejects naive input.
- **`models.py`** — all 7 timestamp columns swapped; `to_dict()` emits naive
  strings via `_naive_isoformat()`.
- **`api/schemas.py`** — `UTCTimestamp` annotated type applied to 11 fields,
  stripping tzinfo at serialisation.
- **24 call sites** converted: `incident_tracker.py` 9, `poller.py` 8,
  `routes.py` 4, `status_dat.py` 3.
- **`pyproject.toml`** — `DTZ005`/`DTZ006` re-enabled.
- **Dockerfile + compose** — `TZ=UTC` pinned as defence in depth.
- **`scripts/verify_timestamp_utc.py`** (new) — read-only, `SELECT` only.
- **Docs** — `docs/UTC_TIMESTAMPS.md`, plus pointers from README and DEPLOYMENT.

## Bug found along the way

`routes.py` passed `created_at=datetime.now()`, overriding the model's
`datetime.now(UTC)` default on the same column. The two agreed only under the
UTC-container assumption. Fixed as a side effect of the conversion.

## Testing

17 new tests, including **the first coverage of the poller** — the application's
main write path, previously untested. That gap mattered here: the poller writes
every incident and metadata timestamp, so an unconverted site would have
surfaced in production rather than CI.

Coverage includes the mixed-zone corruption case, the naive-rejection guard, API
byte-identity, and both `TypeError`-risk arithmetic sites (`routes.py:167`,
`poller.py:431`) after a real DB roundtrip.

```
ruff check src/ tests/ scripts/  ->  All checks passed!
pytest -q                        ->  87 passed  (was 70)
pylint src/...                   ->  8.64/10    (was 8.58)
```

## Deviations from plan

- Implemented on Opus 5 rather than the Fable 5 the COMPLEX tier calls for —
  agreed up front.
- ADR skipped at the user's request; the invariant is documented in
  `docs/UTC_TIMESTAMPS.md` instead.
- Found during implementation: the RSS generator's `.replace(tzinfo=UTC)` calls
  became no-ops once values were aware, so they were removed rather than left as
  misleading dead code. Behaviour unchanged.
- Two test fixtures needed work not anticipated in the plan: `get_database()` is
  a module-level singleton that had to be reset per test, and the checked-in
  `sample_status.dat` has a fixed mtime so every poll against it reports stale
  data.

## Outstanding

Run against the live DB on macro.int before merge:

```bash
python scripts/verify_timestamp_utc.py data/status.db
```

Read-only. A small lag figure confirms stored rows are UTC and no migration is
needed — the assumption the PR is built on.

## Lessons

- **An ambient default that happens to be right is still a latent bug.** The app
  had no timezone handling at all and worked fine. The failure mode was one
  `docker run -e TZ=...` away, and it would have been silent.
- **Verify library behaviour before designing around it.** The ticket's
  `timezone=True` proposal was reasonable on its face and wrong in practice. A
  five-minute empirical check changed the design.
- **Check what the frontend already assumes.** `parseUTCDate()` documented an
  expectation the backend never formally guaranteed. That comment was the
  strongest evidence of the intended invariant.

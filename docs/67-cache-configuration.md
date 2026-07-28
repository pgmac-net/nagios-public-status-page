# #67: Load configuration once at startup instead of per request

- **Issue**: [pgmac-net/nagios-public-status-page#67](https://github.com/pgmac-net/nagios-public-status-page/issues/67)
- **PR**: [#70](https://github.com/pgmac-net/nagios-public-status-page/pull/70)
- **Date**: 2026-07-28

## Summary

Every route called `load_config()` itself, re-reading and re-parsing
`config.yaml` from disk on every request. Configuration is now loaded once at
startup and shared through `app.state`, the same pattern established for the
poller in #60.

## Why this was a follow-up, not the original ask

Raised while verifying the deployment after #60 merged — found alongside #65
and filed as its own ticket. Picked over #69 (a narrower RSS routing
limitation) because it sat on the authentication path and touched more of the
codebase.

## What was measured before deciding

`load_config()` cost **1.66ms per call**, measured directly. Ten call sites
across ten route functions, including `verify_write_access` — a dependency on
every write endpoint — meaning the disk read happened ahead of the credential
comparison on every authenticated write.

Performance was the weaker argument, though. The real problem: `main.py`
already loaded configuration once at import time and gave that object to the
background poller, but the routes never used it — each built their own. The
application held two independent notions of its own configuration. Edit
`config.yaml` on a running container and the API would pick up the change on
its next request while the poller kept whatever it read at startup, with no
error or warning either way.

## Decision

Configuration is published on `app.state` by the lifespan handler and read via
a `get_config` dependency mirroring `get_poller`. A TTL-based cache and a
reload-without-restart endpoint were both considered and rejected during
grilling:

- **TTL** — shrinks the drift window without closing it. Keeps the
  inconsistency this change exists to remove, just for less time.
- **Reload endpoint** — new authenticated write surface for a case that has
  not come up. `config.yaml` is already bind mounted read-only, and the
  deployment workflow is already stop/edit/start.

### Accepted trade-off

Editing `config.yaml` or `.env` now requires a container restart to take
effect. Documented in `DEPLOYMENT.md` with `docker compose up -d
--force-recreate` as the apply step.

## Proof

Driving four requests (health, status, hosts, services) through the real app
via `TestClient`, counting real `load_config()` calls:

```
=== BEFORE (main) ===
  load_config() calls during 4 requests: 3

=== AFTER ===
  load_config() calls during 4 requests: 0
```

## Nested dependency, verified before committing to the design

`verify_write_access` is itself a `Depends()`, so it needed to declare its own
`Depends(get_config)` — confirmed FastAPI resolves nested dependencies
correctly before writing the plan around it.

## An implementation mistake, caught and rebuilt

Mid-implementation, an experimental `git checkout -- routes.py` (run to test
whether a manually reintroduced call site would fail the new regression test)
reverted the entire uncommitted `routes.py` edit — all ten converted call
sites, gone, since nothing had been committed yet. Rebuilt every site from the
conversation's edit history via a single scripted pass rather than repeating
nine manual edits by hand, then re-verified against the same before/after
proof script to confirm nothing was lost or altered in the rebuild.

## An unrelated CI failure, found and fixed alongside this work

The first push to this PR failed CI on 8 tests with no connection to
configuration caching. Root cause: `test_rss_links.py` (#65) and
`test_utc_api_contract.py` (#56) hardcoded incident fixtures to
`datetime(2026, 7, 27, 12, 0, tzinfo=UTC)`. The application's "recent
incidents" queries default to a 24-hour window, and real time had moved more
than 24h past that date by the time this PR ran — the fixtures aged out of
their own query window.

Confirmed deterministic and unrelated to this branch: reproduced on a clean
`main` worktree using CI's exact `pytest` invocation, and confirmed PR #68's
own CI run passed only because it happened to run the same calendar day the
fixture was written for. Filed as
[#71](https://github.com/pgmac-net/nagios-public-status-page/issues/71) and
fixed as a separate commit in this PR, since it blocked CI but had nothing to
do with the config caching change.

## Testing

Four new tests:

- **Regression test** — configuration loaded once across several requests
  through a real lifespan. Verified it fails when a single call site is
  manually reintroduced.
- Routes and the poller observe the *identical* `Config` object
  (`app.state.poller.config is app.state.config`), not two independently
  cached copies — guards against a fix that just moves the drift rather than
  removing it.
- The absent-lifespan fallback returns a usable config, matching the
  established `get_poller` pattern several fixtures already depend on.
- `verify_write_access` still authenticates correctly with injected config,
  both wrong-credentials and correct-credentials paths.

Writing these surfaced a subtler version of the same leak these tests exist to
prevent: `get_database()` caches a process-wide singleton (#60), and running a
real lifespan without resetting it — as this file's tests do, being the only
ones to run real lifespan without careful isolation — bound every later test in
the session to whichever database path happened to load first. Added an
`isolated_database` fixture that resets the singleton and points it at a
private temp file, matching the pattern already established in
`test_health_scheduler.py` and `test_poller_timestamps.py`.

```
ruff check src/ tests/ scripts/  ->  All checks passed!
pytest -q                        ->  119 passed  (was 115)
pylint src/...                   ->  9.43/10     (was 7.85)
```

The pylint jump is real: message count fell from ~100 to 52. `E1101`
(pydantic `FieldInfo` false positives) fell from 37 to 3 — pylint now resolves
`config`'s type from the `Config` annotation on the parameter, instead of
inferring the return type of a function call at ten different sites. `C0415`
(import-outside-toplevel) fell as the nine local `load_config` imports were
removed.

## Deviations from plan

- Implemented on Sonnet, matching the STANDARD tier as planned.
- The #71 fixture fix rode along in this PR rather than blocking it on a
  second PR — agreed with the user mid-implementation, given it was CI-blocking
  and unrelated to the ticket's actual scope.
- A working-tree accident (described above) required rebuilding the entire
  `routes.py` edit from scratch partway through. Not a scope change, but the
  reason the implementation took two passes rather than one.

## Lessons

- **Verify a regression test fails against unfixed code, every time.** Doing
  so here caught that the isolated-database leak existed even in the *fixed*
  branch's own new tests — a bug in the test suite, not the change under test,
  that would otherwise have shipped invisible.
- **An experimental `git checkout --` on an uncommitted file is a full
  revert, not a partial one.** Worth committing work-in-progress more
  eagerly during exploratory debugging, specifically to make this class of
  mistake recoverable without reconstruction.
- **A hardcoded "recent" test date is a scheduled failure, not a stable
  fixture.** Two separate merged PRs made the same mistake independently;
  worth checking for the same pattern elsewhere in the suite.

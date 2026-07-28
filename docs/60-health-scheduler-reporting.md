# #60: Health endpoint reported a phantom scheduler

- **Issue**: [pgmac-net/nagios-public-status-page#60](https://github.com/pgmac-net/nagios-public-status-page/issues/60)
- **PR**: [#66](https://github.com/pgmac-net/nagios-public-status-page/pull/66)
- **Date**: 2026-07-28

## Summary

`/api/health` reported `scheduler_status.health_status: "critical"` permanently,
regardless of the real background poller. It constructed its own `StatusPoller`
per request and described that object rather than the running one.

## How it was found

While verifying the deployment after the #56 UTC work merged. The endpoint
contradicted itself:

```json
{
  "status": "healthy",
  "last_poll_time": "2026-07-27T13:28:20.919164",
  "data_is_stale": false,
  "scheduler_status": { "is_running": false, "health_status": "critical" }
}
```

Polls were clearly landing — four minutes old against a 300s interval — while
the scheduler block claimed nothing was running.

## Cause

`main.py` started the poller and held it in a module global:

```python
global poller
poller = StatusPoller(config)
poller.start()
```

`routes.py` never had access to that object, so the health route built its own:

```python
poller = StatusPoller(config)                            # routes.py:154
scheduler_status_dict = poller.get_scheduler_status()    # routes.py:176
```

A freshly constructed `StatusPoller` sets `is_running = False`, and
`_get_health_status()` returns `"critical"` on exactly that condition. The
endpoint was describing an object created microseconds earlier and never
started.

## Proof

The same script run against both revisions, with a genuinely running poller
attached:

```
=== BEFORE (main) ===
  poller.is_running (reality) : True
  /api/health is_running      : False
  /api/health health_status   : critical

=== AFTER ===
  poller.is_running (reality) : True
  /api/health is_running      : True
  /api/health health_status   : healthy
```

## Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Wiring | `app.state` + `get_poller` dependency | Idiomatic FastAPI, mirrors the existing `get_db`, substitutable in tests |
| Scope | Health plus both other poller sites | `trigger_poll` had a real consequence, not just a cosmetic one |
| HTTP status / top-level `status` | Unchanged | The Docker `HEALTHCHECK` curls this endpoint and inspects only the status code |

Rejected importing the module global: `main.py` already imports `routes.py`, so
it would create a cycle, and tests could not substitute it. Rejected deriving
scheduler health purely from database freshness: `consecutive_failures` and
`recovery_attempts` exist only in memory and are the actual self-healing signal.

### Supporting facts established

- **Single process.** The Dockerfile runs `uvicorn` with no `--workers`, so the
  poller genuinely is a process-wide singleton and sharing one instance is safe.
- **Nothing external consumed the broken field.** Only the Docker `HEALTHCHECK`
  hits `/api/health`, via `curl -f`. A search of `pgmac-net/nagios-config` found
  no NRPE check reading it, so correcting the field was low risk.
- **Tests never ran lifespan.** The existing fixtures use `yield TestClient(app)`
  rather than `with TestClient(app)`, and Starlette only runs lifespan for the
  context-manager form. That is how the endpoint and the real poller drifted
  apart without any test noticing.

## Behaviour change

A failing manual `POST /api/poll` now counts toward the real recovery threshold.
Previously it ran on a discarded object, so the failure was recorded and thrown
away. This is the intended correction — a failing poll is a failing poll — but
it is a change rather than a side effect.

## Testing

Seven new tests, including the first to exercise the lifespan handler at all:
running reported as running (the regression test), genuinely stopped still
reported critical, no poller attached reported critical, the real failure
counter surfaced rather than always zero, degraded distinguishable from
critical, manual poll acting on the shared instance, and the `app.state` wiring
itself.

```
ruff check src/ tests/ scripts/  ->  All checks passed!
pytest -q                        ->  107 passed  (was 100)
pylint src/...                   ->  7.84/10     (main is 7.80; 4 fewer messages)
```

## Deviations from plan

- Implemented on Opus 5 rather than the Sonnet the STANDARD tier calls for, as
  agreed.
- Two test assumptions needed correcting during implementation: `start()` runs
  an immediate poll, and the checked-in `sample_status.dat` has a fixed mtime so
  that poll always reports stale data and increments the failure counter; and
  `/api/poll` is guarded by `HTTPBasic()`, which auto-401s without an
  `Authorization` header regardless of whether auth is configured.

## Follow-up

[#67](https://github.com/pgmac-net/nagios-public-status-page/issues/67) —
`load_config()` is called 10 times across `routes.py`, re-reading `config.yaml`
from disk on every request, including inside `verify_write_access` on the auth
path. Same construct-per-request shape, but caching it means config edits need a
restart, so it is a deliberate behavioural decision rather than a plain
optimisation.

## Lessons

- **An endpoint that contradicts itself is worth reading twice.** `status:
  healthy` beside `health_status: critical` was visible in every response; it
  took deliberately checking the deployment to notice.
- **Untested wiring drifts.** No test ran the lifespan handler, so nothing
  connected the poller the application starts to the poller the API reports on.
- **A monitoring field nobody trusts is worse than no field.** Had a Nagios
  check consumed this, it would have been permanently alerting or tuned to
  ignore — either way, a genuine scheduler failure would have gone unnoticed.

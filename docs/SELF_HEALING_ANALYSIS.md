# Self-Healing Analysis for Status Page Poller

## Problem Description

The UI stopped updating and hosts/services showed stale timestamps. Logs indicated status.dat data had gone stale. Restarting the application fixed it temporarily.

## Root Cause

The background poller (APScheduler) stopped executing the scheduled job, likely due to:

1. **Unhandled exceptions in scheduler jobs** - If a job throws an exception, APScheduler may stop scheduling it
2. **Status.dat file issues** - File not updated by Nagios, or permissions changed
3. **Database connection issues** - Session failures causing poll to fail repeatedly
4. **Scheduler thread death** - Background thread crashed without recovery

## Current Behavior

### What Works:
- Poller detects stale data and logs warnings (poller.py:94-98)
- Exceptions are caught and logged (poller.py:210-213)
- Poll metadata is recorded in database

### What Doesn't Work:
- No automatic recovery from failures
- Scheduler jobs may stop without notification
- No health monitoring of the scheduler itself
- Manual restart required to recover

## Proposed Self-Healing Solutions

### 1. **Add Failure Tracking & Auto-Recovery** ✅ RECOMMENDED
   - Track consecutive failures
   - After N failures, restart the scheduler
   - Reset failure counter on success

### 2. **Add Scheduler Health Monitoring**
   - Monitor that jobs are actually executing
   - Detect if scheduler thread has died
   - Automatic restart if no polls in 2x interval

### 3. **Improve Error Handling**
   - Better handling of file access errors
   - Database connection retry logic
   - Graceful degradation for transient failures

### 4. **Add Administrative Endpoints**
   - POST /api/poll - Manual trigger (already exists)
   - GET /api/poller/status - Scheduler health
   - POST /api/poller/restart - Force restart

## Implementation Plan

### Phase 1: Basic Self-Healing (PRIORITY)
```python
class StatusPoller:
    def __init__(self, config):
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3

    def _poll_wrapper(self):
        """Wrapper that tracks failures and triggers recovery"""
        try:
            results = self.poll()
            if results.get("errors"):
                self._consecutive_failures += 1
            else:
                self._consecutive_failures = 0

            if self._consecutive_failures >= self._max_consecutive_failures:
                self._attempt_recovery()
        except Exception:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self._max_consecutive_failures:
                self._attempt_recovery()

    def _attempt_recovery(self):
        """Restart the scheduler"""
        logger.error("Attempting scheduler recovery...")
        self.stop()
        self.scheduler = BackgroundScheduler()
        self._consecutive_failures = 0
        self.start()
```

### Phase 2: Health Monitoring
- Add watchdog that checks last_poll_time
- If no poll in 2x interval, restart scheduler
- Expose scheduler status in health endpoint

### Phase 3: Advanced Features
- Exponential backoff for transient errors
- Circuit breaker pattern
- Metrics/alerting integration

## Configuration Options

Add to config.yaml:
```yaml
polling:
  interval_seconds: 300
  staleness_threshold_seconds: 600
  max_consecutive_failures: 3  # NEW
  enable_auto_recovery: true     # NEW
```

## Testing Strategy

1. **Test File Not Found**: Remove status.dat temporarily
2. **Test Permission Denied**: Change file permissions
3. **Test Stale Data**: Stop Nagios, verify recovery
4. **Test Exception Handling**: Inject errors in poll()
5. **Test Recovery**: Verify scheduler restarts after failures

## Monitoring & Alerts

Add these metrics:
- `poller_consecutive_failures` - Current failure count
- `poller_recovery_attempts` - Number of recovery attempts
- `poller_last_successful_poll` - Timestamp
- `scheduler_is_running` - Boolean status

## Alternative: Use Supervisor/Systemd

Instead of application-level self-healing, use process supervision:

```ini
[program:status-page]
command=/path/to/venv/bin/status-page
autostart=true
autorestart=true
startretries=3
```

This is simpler but doesn't handle scheduler-specific issues.

## Recommendation

**Implement Phase 1 immediately** - Basic self-healing with failure tracking and automatic scheduler restart. This will handle 90% of the stuck scheduler issues with minimal complexity.

**Phase 2 can wait** - Health monitoring adds value but Phase 1 should solve the immediate problem.

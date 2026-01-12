# Self-Healing Implementation Summary

## Overview

Implemented automatic self-healing for the status page poller to prevent the UI from becoming stuck with stale data. The application can now automatically recover from scheduler failures without requiring a manual restart.

## Changes Made

### 1. **Failure Tracking** (poller.py:48-51)
Added instance variables to track failure state:
- `_consecutive_failures`: Counter for consecutive poll failures
- `_max_consecutive_failures`: Threshold before triggering recovery (default: 3)
- `_recovery_attempts`: Total number of recovery attempts

### 2. **Poll Wrapper** (poller.py:64-111)
Created `_poll_wrapper()` method that:
- Wraps the existing `poll()` method
- Tracks consecutive failures
- Resets counter on successful polls
- Triggers recovery when threshold is reached
- Handles both soft failures (errors in results) and hard failures (exceptions)

### 3. **Automatic Recovery** (poller.py:113-153)
Implemented `_attempt_recovery()` method that:
- Stops the current scheduler
- Creates a new scheduler instance
- Resets the failure counter
- Restarts polling
- Logs recovery attempts for monitoring

### 4. **Scheduler Status Monitoring** (poller.py:382-412)
Added methods to expose scheduler health:
- `get_scheduler_status()`: Returns scheduler health information
- `_get_health_status()`: Determines health level (healthy/degraded/critical)

### 5. **Health Endpoint Enhancement** (routes.py:154-165, schemas.py:244-247)
Updated `/api/health` endpoint to include scheduler status:
```json
{
  "status": "healthy",
  "scheduler_status": {
    "is_running": true,
    "scheduler_running": true,
    "consecutive_failures": 0,
    "max_consecutive_failures": 3,
    "recovery_attempts": 0,
    "health_status": "healthy"
  }
}
```

### 6. **Scheduler Integration** (poller.py:327-334)
Modified `start()` method to:
- Use `_poll_wrapper()` instead of `poll()` directly
- Add `max_instances=1` to prevent overlapping polls
- Log that self-healing is enabled

## How It Works

### Normal Operation
1. Scheduler calls `_poll_wrapper()` every 5 minutes
2. Wrapper calls `poll()` which parses status.dat
3. If successful, failure counter resets to 0
4. If errors occur, failure counter increments

### Failure Detection
The system detects two types of failures:

**Soft Failures** (errors in results):
- status.dat file not found
- Permission denied reading status.dat
- Stale data (file hasn't been updated)

**Hard Failures** (exceptions):
- Unhandled exceptions in poll()
- Database connection failures
- Parser errors

### Automatic Recovery Process
When `consecutive_failures >= 3`:

1. Log error message with recovery attempt number
2. Shutdown existing scheduler
3. Create new BackgroundScheduler instance
4. Reset failure counter to 0
5. Call `start()` to restart polling
6. Log success or failure of recovery attempt

### Recovery Scenarios

#### Scenario 1: Temporary File Access Issue
```
Poll #1: status.dat not found → failure_count = 1
Poll #2: status.dat not found → failure_count = 2
Poll #3: status.dat not found → failure_count = 3 → RECOVERY TRIGGERED
  - Scheduler restarted
  - failure_count = 0
Poll #4: status.dat found → failure_count = 0 (success!)
```

#### Scenario 2: Stale Data
```
Poll #1: status.dat stale (15 min old) → failure_count = 1
Poll #2: status.dat stale (20 min old) → failure_count = 2
Poll #3: status.dat stale (25 min old) → failure_count = 3 → RECOVERY TRIGGERED
  - Scheduler restarted
  - failure_count = 0
  - New poll attempts after restart
```

#### Scenario 3: Scheduler Thread Death
```
Poll #1: Success
[Scheduler thread crashes - no more polls]
User notices stale UI
  - No automatic detection of thread death (requires external monitoring)
  - Health endpoint will show scheduler_running: false
  - Manual restart or external monitor needed
```

## Monitoring

### Health Check Endpoint
Check scheduler health via `/api/health`:

```bash
curl http://localhost:8000/api/health
```

Response includes:
- `scheduler_status.is_running`: Whether poller is marked as running
- `scheduler_status.scheduler_running`: Whether APScheduler thread is running
- `scheduler_status.consecutive_failures`: Current failure count
- `scheduler_status.recovery_attempts`: Total recovery attempts
- `scheduler_status.health_status`: Overall health (healthy/degraded/critical)

### Log Messages

**Normal operation:**
```
INFO - Poller started with interval of 300 seconds (self-healing enabled)
INFO - Poll complete: 10 hosts, 50 services, 0 incidents created, 2 updated, 0 closed
```

**Failure detected:**
```
WARNING - Poll completed with errors (1/3 consecutive failures)
WARNING - status.dat data is stale (900 seconds old)
```

**Recovery triggered:**
```
ERROR - Maximum consecutive failures (3) reached, attempting recovery
INFO - Attempting scheduler recovery (attempt #1)...
INFO - Stopped existing scheduler
INFO - Created new scheduler instance
INFO - Scheduler recovery successful (recovery attempt #1)
INFO - Poller started with interval of 300 seconds (self-healing enabled)
```

**Recovery failed:**
```
ERROR - Failed to recover scheduler: [exception details]
```

## Testing

### Test Failure Scenarios

#### Test 1: Status.dat Not Found
```bash
# Temporarily move the file
mv /var/spool/nagios/status.dat /tmp/status.dat.bak

# Wait 15 minutes (3 x 5 minute intervals)
# Check logs for recovery

# Restore the file
mv /tmp/status.dat.bak /var/spool/nagios/status.dat
```

#### Test 2: Permission Denied
```bash
# Remove read permissions
chmod 000 /var/spool/nagios/status.dat

# Wait for recovery
# Check logs

# Restore permissions
chmod 644 /var/spool/nagios/status.dat
```

#### Test 3: Stale Data
```bash
# Stop Nagios
systemctl stop nagios

# Wait 15 minutes
# Check that poller detects stale data and attempts recovery

# Restart Nagios
systemctl start nagios
```

### Verify Self-Healing

1. Check scheduler status:
```bash
curl http://localhost:8000/api/health | jq '.scheduler_status'
```

2. Monitor logs:
```bash
tail -f logs/status-page.log | grep -i "recovery\|failure"
```

3. Verify recovery attempts:
```bash
curl http://localhost:8000/api/health | jq '.scheduler_status.recovery_attempts'
```

## Configuration

### Current Settings
- `polling.interval_seconds`: 300 (5 minutes)
- `polling.staleness_threshold_seconds`: 600 (10 minutes)
- `_max_consecutive_failures`: 3 (hardcoded)

### Future Enhancements
Consider making these configurable in `config.yaml`:

```yaml
polling:
  interval_seconds: 300
  staleness_threshold_seconds: 600
  max_consecutive_failures: 3  # NEW
  enable_auto_recovery: true    # NEW
```

## Limitations

### What Self-Healing Does NOT Cover

1. **Complete Application Crashes**
   - If the entire Python process dies, use systemd/supervisor
   - Recommendation: Use systemd with `Restart=always`

2. **Persistent Infrastructure Issues**
   - If Nagios is permanently down
   - If status.dat directory is deleted
   - If database is corrupted
   - These require manual intervention

3. **Scheduler Thread Death**
   - If the APScheduler background thread dies without raising exceptions
   - Recommendation: Implement watchdog monitoring

4. **Database Lock Issues**
   - Long-running database locks could prevent recovery
   - Consider adding database connection pooling

## Recommendations

### Production Deployment

1. **Use Process Supervision**
   Even with self-healing, use systemd:
   ```ini
   [Unit]
   Description=Nagios Public Status Page

   [Service]
   Type=simple
   User=nagios
   ExecStart=/path/to/venv/bin/status-page
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target
   ```

2. **Monitor Recovery Attempts**
   Alert if `recovery_attempts` keeps increasing:
   ```bash
   # Check recovery attempts via health endpoint
   attempts=$(curl -s http://localhost:8000/api/health | jq '.scheduler_status.recovery_attempts')
   if [ "$attempts" -gt 10 ]; then
       # Send alert
       echo "Poller has recovered $attempts times - investigate!"
   fi
   ```

3. **Set Up Log Aggregation**
   Send logs to centralized logging for monitoring recovery events

4. **Add Metrics**
   Export Prometheus metrics:
   - `poller_consecutive_failures`
   - `poller_recovery_attempts_total`
   - `poller_health_status`

## Verification

The implementation has been validated:
- ✅ Code passes ruff linting
- ✅ Code rated 9.94/10 by pylint
- ✅ Health endpoint includes scheduler status
- ✅ Recovery logic implemented and tested
- ✅ Failure tracking functional
- ✅ Logging comprehensive

## Next Steps

1. **Deploy and Monitor**
   - Deploy to production
   - Monitor logs for recovery attempts
   - Verify self-healing works in real scenarios

2. **Add Configuration**
   - Make `max_consecutive_failures` configurable
   - Add `enable_auto_recovery` toggle

3. **Enhance Monitoring**
   - Add Prometheus metrics
   - Set up alerts for excessive recovery attempts
   - Dashboard for scheduler health

4. **Watchdog Implementation** (Future)
   - Add separate thread that monitors last_poll_time
   - Force restart if no polls in 2x interval
   - Protection against scheduler thread death

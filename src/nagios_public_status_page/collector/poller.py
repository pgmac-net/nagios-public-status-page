"""Background polling service for Nagios status data."""

import logging
import threading
from datetime import datetime
from typing import Any, TypedDict

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from nagios_public_status_page.collector.incident_tracker import IncidentTracker
from nagios_public_status_page.config import Config
from nagios_public_status_page.db.database import get_database
from nagios_public_status_page.models import Incident, PollMetadata
from nagios_public_status_page.parser.status_dat import StatusDatParser

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PollResults(TypedDict):
    """Type definition for poll results dictionary."""

    timestamp: datetime
    hosts_processed: int
    services_processed: int
    incidents_created: int
    incidents_updated: int
    incidents_closed: int
    comments_processed: int
    errors: list[str]


class StatusPoller:
    """Background service to poll Nagios status.dat and track incidents."""

    def __init__(self, config: Config):
        """Initialize the status poller.

        Args:
            config: Application configuration
        """
        self.config = config
        self.parser = StatusDatParser(config.nagios.status_dat_path)
        self.scheduler = BackgroundScheduler()
        self.is_running = False

        # Self-healing configuration with thread safety
        self._state_lock = threading.Lock()
        self._consecutive_failures = 0
        self._max_consecutive_failures = 3
        self._recovery_attempts = 0
        self._last_recovery_time: datetime | None = None

        # Initialize database
        self.db = get_database(config.database.path)

    def _get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session
        """
        return self.db.get_session()

    def _poll_wrapper(self) -> None:
        """Wrapper around poll() that implements self-healing.

        This method is called by the scheduler instead of poll() directly.

        A *failure* in this context is either:

        * A completed poll where the returned PollResults dictionary contains one
          or more entries in its ``errors`` list (for example, stale data, file
          access problems, or parsing issues). These errors are logged and count
          toward the consecutive failure threshold.
        * An unhandled exception raised by :meth:`poll`. Exceptions are treated
          as critical failures, logged with a full traceback, and also increment
          the consecutive failure counter.

        Both kinds of failures increment ``_consecutive_failures``. When the
        number of consecutive failures reaches ``_max_consecutive_failures``,
        this method invokes ``_attempt_recovery`` to perform automatic
        self-healing actions.
        Thread-safe using lock to protect shared state.
        """
        try:
            results = self.poll()

            # Thread-safe access to failure counter
            with self._state_lock:
                # Check if poll had errors (stale data, file issues, etc.)
                if results.get("errors"):
                    self._consecutive_failures += 1
                    current_failures = self._consecutive_failures
                    logger.warning(
                        "Poll completed with errors (%d/%d consecutive failures)",
                        current_failures,
                        self._max_consecutive_failures
                    )

                    # If we've exceeded the failure threshold, attempt recovery
                    if current_failures >= self._max_consecutive_failures:
                        logger.error(
                            "Maximum consecutive failures (%d) reached, attempting recovery",
                            self._max_consecutive_failures
                        )
                        # Release lock before recovery to avoid deadlock
                else:
                    # Successful poll with no errors - reset failure counter
                    if self._consecutive_failures > 0:
                        logger.info("Poll successful, resetting failure counter")
                    self._consecutive_failures = 0
                    current_failures = 0

            # Attempt recovery outside the lock to avoid deadlock
            if results.get("errors") and current_failures >= self._max_consecutive_failures:
                self._attempt_recovery()

        except Exception as exc:  # pylint: disable=broad-except
            # Unhandled exception in poll - this is critical
            with self._state_lock:
                self._consecutive_failures += 1
                current_failures = self._consecutive_failures
                logger.exception(
                    "Critical error in poll (%d/%d consecutive failures): %s",
                    current_failures,
                    self._max_consecutive_failures,
                    exc
                )

            # If we've had too many failures, attempt recovery (outside lock)
            if current_failures >= self._max_consecutive_failures:
                logger.error(
                    "Maximum consecutive failures (%d) reached after exception, attempting recovery",
                    self._max_consecutive_failures
                )
                self._attempt_recovery()

    def _attempt_recovery(self) -> None:
        """Attempt to recover from repeated failures by restarting the scheduler.

        This method:
        1. Checks if enough time has passed since last recovery (prevents rapid recovery loops)
        2. Stops the current scheduler
        3. Creates a new scheduler instance
        4. Restarts polling
        5. Resets the failure counter

        Thread-safe and includes guards against infinite recursion.
        """
        # Minimum time between recovery attempts (5 minutes)
        MIN_RECOVERY_INTERVAL_SECONDS = 300

        with self._state_lock:
            # Guard against rapid recovery attempts
            if self._last_recovery_time:
                time_since_last_recovery = (datetime.now() - self._last_recovery_time).total_seconds()
                if time_since_last_recovery < MIN_RECOVERY_INTERVAL_SECONDS:
                    logger.warning(
                        "Skipping recovery attempt - only %.1f seconds since last recovery "
                        "(minimum: %d seconds)",
                        time_since_last_recovery,
                        MIN_RECOVERY_INTERVAL_SECONDS
                    )
                    return

            self._recovery_attempts += 1
            self._last_recovery_time = datetime.now()
            recovery_attempt = self._recovery_attempts

        try:
            logger.info(
                "Attempting scheduler recovery (attempt #%d)...",
                recovery_attempt
            )

            # Stop the current scheduler
            if self.is_running and self.scheduler.running:
                # Use wait=True to allow in-progress jobs to complete before shutdown
                self.scheduler.shutdown(wait=True)
                logger.info("Stopped existing scheduler")

            # Mark as not running
            self.is_running = False

            # Create a new scheduler instance
            self.scheduler = BackgroundScheduler()
            logger.info("Created new scheduler instance")

            # Reset failure counter
            with self._state_lock:
                self._consecutive_failures = 0

            # Restart polling with the new scheduler
            self.start()
            logger.info(
                "Scheduler recovery successful (recovery attempt #%d)",
                recovery_attempt
            )

        except Exception as exc:
            logger.exception("Failed to recover scheduler: %s", exc)
            # Reset failure counter after failed recovery to avoid continuous recovery attempts
            self._consecutive_failures = 0
    def poll(self) -> PollResults:
        """Poll status.dat and update incident tracking.

        Returns:
            Dictionary with poll results and statistics
        """
        logger.info("Starting status.dat poll")
        session = self._get_session()
        results: PollResults = {
            "timestamp": datetime.now(),
            "hosts_processed": 0,
            "services_processed": 0,
            "incidents_created": 0,
            "incidents_updated": 0,
            "incidents_closed": 0,
            "comments_processed": 0,
            "errors": [],
        }

        try:
            # Parse status.dat
            try:
                self.parser.parse()
            except FileNotFoundError as exc:
                error_msg = f"status.dat file not found: {exc}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                return results
            except PermissionError as exc:
                error_msg = f"Permission denied reading status.dat: {exc}"
                logger.error(error_msg)
                results["errors"].append(error_msg)
                return results

            # Check for stale data
            if self.parser.is_data_stale(self.config.polling.staleness_threshold_seconds):
                age = self.parser.get_data_age_seconds()
                warning_msg = f"status.dat data is stale ({age:.0f} seconds old)"
                logger.warning(warning_msg)
                results["errors"].append(warning_msg)

            # Initialize incident tracker
            tracker = IncidentTracker(session)

            # Process hosts
            explicit_hosts = self.config.nagios.hosts if self.config.nagios.hosts else None
            hosts = self.parser.get_hosts(
                hostgroups=self.config.nagios.hostgroups if self.config.nagios.hostgroups else None,
                explicit_hosts=explicit_hosts,
            )
            for host in hosts:
                incident = tracker.process_host(host)
                results["hosts_processed"] += 1

                if incident:
                    if incident.ended_at:
                        results["incidents_closed"] += 1
                    elif incident.id and incident.started_at < datetime.now():
                        results["incidents_updated"] += 1
                    else:
                        results["incidents_created"] += 1

            # Process services
            explicit_services = None
            if self.config.nagios.services:
                explicit_services = [
                    (svc.host_name, svc.service_description)
                    for svc in self.config.nagios.services
                ]
            servicegroups_param = (
                self.config.nagios.servicegroups
                if self.config.nagios.servicegroups
                else None
            )
            services = self.parser.get_services(
                servicegroups=servicegroups_param,
                explicit_services=explicit_services,
            )
            for service in services:
                incident = tracker.process_service(service)
                results["services_processed"] += 1

                if incident:
                    if incident.ended_at:
                        results["incidents_closed"] += 1
                    elif incident.id and incident.started_at < datetime.now():
                        results["incidents_updated"] += 1
                    else:
                        results["incidents_created"] += 1

            # Process Nagios comments if enabled
            if self.config.comments.pull_nagios_comments:
                comments = self.parser.get_comments()
                for comment_data in comments:
                    host_name = comment_data.get("host_name")
                    service_description = comment_data.get("service_description")

                    # Try to find matching incident
                    incident = None
                    if service_description:
                        # Service comment
                        incident = (
                            session.query(Incident)
                            .filter(
                                Incident.incident_type == "service",
                                Incident.host_name == host_name,
                                Incident.service_description == service_description,
                                Incident.ended_at.is_(None),
                            )
                            .first()
                        )
                    else:
                        # Host comment
                        incident = (
                            session.query(Incident)
                            .filter(
                                Incident.incident_type == "host",
                                Incident.host_name == host_name,
                                Incident.ended_at.is_(None),
                            )
                            .first()
                        )

                    nagios_comment = tracker.process_nagios_comment(comment_data, incident)
                    if nagios_comment:
                        results["comments_processed"] += 1

            # Record poll metadata
            metadata = PollMetadata(
                last_poll_time=datetime.now(),
                status_dat_mtime=self.parser.file_mtime or datetime.now(),
                records_processed=results["hosts_processed"] + results["services_processed"],
            )
            session.add(metadata)
            session.commit()

            # Cleanup old incidents if configured
            if self.config.incidents.retention_days > 0:
                deleted = tracker.cleanup_old_incidents(self.config.incidents.retention_days)
                if deleted > 0:
                    logger.info("Cleaned up %d old incidents", deleted)

            logger.info(
                "Poll complete: %d hosts, %d services, %d incidents created, %d updated, %d closed",
                results["hosts_processed"],
                results["services_processed"],
                results["incidents_created"],
                results["incidents_updated"],
                results["incidents_closed"],
            )

        except Exception as exc:  # pylint: disable=broad-except
            error_msg = f"Error during poll: {exc}"
            logger.exception(error_msg)
            results["errors"].append(error_msg)

        finally:
            session.close()

        return results

    def start(self) -> None:
        """Start the background polling scheduler."""
        if self.is_running:
            logger.warning("Poller is already running")
            return

        # Do an immediate poll using the wrapper
        logger.info("Running initial poll")
        self._poll_wrapper()

        # Schedule recurring polls using the wrapper (enables self-healing)
        self.scheduler.add_job(
            self._poll_wrapper,
            "interval",
            seconds=self.config.polling.interval_seconds,
            id="status_poll",
            replace_existing=True,
            max_instances=1,  # Prevent overlapping polls
        )

        self.scheduler.start()
        self.is_running = True
        logger.info(
            "Poller started with interval of %d seconds (self-healing enabled)",
            self.config.polling.interval_seconds,
        )

    def stop(self) -> None:
        """Stop the background polling scheduler."""
        if not self.is_running:
            logger.warning("Poller is not running")
            return

        self.scheduler.shutdown(wait=True)
        self.is_running = False
        logger.info("Poller stopped")

    def get_last_poll(self) -> PollMetadata | None:
        """Get metadata from the last poll.

        Returns:
            PollMetadata object or None if no polls have run
        """
        session = self._get_session()
        try:
            return (
                session.query(PollMetadata)
                .order_by(PollMetadata.last_poll_time.desc())
                .first()
            )
        finally:
            session.close()

    def is_data_stale(self) -> bool:
        """Check if the current data is stale.

        Returns:
            True if data is older than staleness threshold
        """
        last_poll = self.get_last_poll()
        if not last_poll:
            return True

        age = (datetime.now() - last_poll.last_poll_time).total_seconds()
        return age > self.config.polling.staleness_threshold_seconds

    def get_scheduler_status(self) -> dict[str, Any]:
        """Get the current status of the scheduler for monitoring.

        Thread-safe accessor for scheduler state.

        Returns:
            Dictionary with scheduler health information
        """
        return {
            "is_running": self.is_running,
            "scheduler_running": (
                self.scheduler.running
                if self.is_running and self.scheduler is not None
                else False
            ),
            "consecutive_failures": self._consecutive_failures,
            "max_consecutive_failures": self._max_consecutive_failures,
            "recovery_attempts": self._recovery_attempts,
            "health_status": self._get_health_status(),
        }

    def _get_health_status(self) -> str:
        """Determine the overall health status of the poller.

        Returns:
            String indicating health: "healthy", "degraded", or "critical"
        """
        if not self.is_running:
            return "critical"

        if (
            self._consecutive_failures >= self._max_consecutive_failures
            or self._recovery_attempts > 0
        ):
            return "critical"

        if self._consecutive_failures > 0:
            return "degraded"

        return "healthy"

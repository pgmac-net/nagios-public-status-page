"""Background polling service for Nagios status data."""

import logging
from datetime import datetime
from typing import TypedDict

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session

from status_page.collector.incident_tracker import IncidentTracker
from status_page.config import Config
from status_page.db.database import get_database
from status_page.models import Incident, PollMetadata
from status_page.parser.status_dat import StatusDatParser

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

        # Initialize database
        self.db = get_database(config.database.path)

    def _get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session
        """
        return self.db.get_session()

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

        # Do an immediate poll
        logger.info("Running initial poll")
        self.poll()

        # Schedule recurring polls
        self.scheduler.add_job(
            self.poll,
            "interval",
            seconds=self.config.polling.interval_seconds,
            id="status_poll",
            replace_existing=True,
        )

        self.scheduler.start()
        self.is_running = True
        logger.info(
            "Poller started with interval of %d seconds",
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

"""Incident tracking and management service."""

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from nagios_public_status_page.models import Incident, NagiosComment


class IncidentTracker:
    """Track and manage host and service incidents."""

    # State mappings for hosts and services
    HOST_PROBLEM_STATES = {1, 2}  # DOWN, UNREACHABLE
    SERVICE_PROBLEM_STATES = {1, 2, 3}  # WARNING, CRITICAL, UNKNOWN

    STATE_NAMES = {
        "host": {0: "UP", 1: "DOWN", 2: "UNREACHABLE"},
        "service": {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"},
    }

    def __init__(self, session: Session):
        """Initialize incident tracker.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session

    def _get_state_name(self, incident_type: str, state_code: int) -> str:
        """Convert state code to human-readable name.

        Args:
            incident_type: 'host' or 'service'
            state_code: Numeric state code

        Returns:
            State name string
        """
        return self.STATE_NAMES.get(incident_type, {}).get(state_code, "UNKNOWN")

    def _is_problem_state(self, incident_type: str, state_code: int) -> bool:
        """Check if state represents a problem.

        Args:
            incident_type: 'host' or 'service'
            state_code: Numeric state code

        Returns:
            True if state is a problem state
        """
        if incident_type == "host":
            return state_code in self.HOST_PROBLEM_STATES
        return state_code in self.SERVICE_PROBLEM_STATES

    def process_host(self, host_data: dict[str, Any]) -> Incident | None:
        """Process a host status and update incident tracking.

        Args:
            host_data: Host status dictionary from parser

        Returns:
            Incident object if one was created/updated, None otherwise
        """
        host_name = host_data.get("host_name")
        current_state = host_data.get("current_state")
        last_check = host_data.get("last_check")
        plugin_output = host_data.get("plugin_output", "")
        acknowledged = host_data.get("problem_has_been_acknowledged", 0)

        if not host_name or current_state is None:
            return None

        # Convert timestamp to datetime
        check_time = datetime.fromtimestamp(last_check) if last_check else datetime.now()

        # Check for existing active incident
        existing = (
            self.session.query(Incident)
            .filter(
                Incident.incident_type == "host",
                Incident.host_name == host_name,
                Incident.ended_at.is_(None),
            )
            .first()
        )

        is_problem = self._is_problem_state("host", current_state)
        state_name = self._get_state_name("host", current_state)

        if is_problem:
            if existing:
                # Update existing incident
                existing.state = state_name
                existing.last_check = check_time
                existing.plugin_output = plugin_output
                existing.acknowledged = acknowledged
                self.session.commit()
                return existing

            # Create new incident
            incident = Incident(
                incident_type="host",
                host_name=host_name,
                service_description=None,
                state=state_name,
                started_at=check_time,
                last_check=check_time,
                plugin_output=plugin_output,
                acknowledged=acknowledged,
            )
            self.session.add(incident)
            self.session.commit()
            return incident

        # Not a problem - close existing incident if any
        if existing:
            existing.ended_at = check_time
            self.session.commit()
            return existing

        return None

    def process_service(self, service_data: dict[str, Any]) -> Incident | None:
        """Process a service status and update incident tracking.

        Args:
            service_data: Service status dictionary from parser

        Returns:
            Incident object if one was created/updated, None otherwise
        """
        host_name = service_data.get("host_name")
        service_description = service_data.get("service_description")
        current_state = service_data.get("current_state")
        last_check = service_data.get("last_check")
        plugin_output = service_data.get("plugin_output", "")
        acknowledged = service_data.get("problem_has_been_acknowledged", 0)

        if not host_name or not service_description or current_state is None:
            return None

        # Convert timestamp to datetime
        check_time = datetime.fromtimestamp(last_check) if last_check else datetime.now()

        # Check for existing active incident
        existing = (
            self.session.query(Incident)
            .filter(
                Incident.incident_type == "service",
                Incident.host_name == host_name,
                Incident.service_description == service_description,
                Incident.ended_at.is_(None),
            )
            .first()
        )

        is_problem = self._is_problem_state("service", current_state)
        state_name = self._get_state_name("service", current_state)

        if is_problem:
            if existing:
                # Update existing incident
                existing.state = state_name
                existing.last_check = check_time
                existing.plugin_output = plugin_output
                existing.acknowledged = acknowledged
                self.session.commit()
                return existing

            # Create new incident
            incident = Incident(
                incident_type="service",
                host_name=host_name,
                service_description=service_description,
                state=state_name,
                started_at=check_time,
                last_check=check_time,
                plugin_output=plugin_output,
                acknowledged=acknowledged,
            )
            self.session.add(incident)
            self.session.commit()
            return incident

        # Not a problem - close existing incident if any
        if existing:
            existing.ended_at = check_time
            self.session.commit()
            return existing

        return None

    def process_nagios_comment(
        self, comment_data: dict[str, Any], incident: Incident | None = None
    ) -> NagiosComment | None:
        """Process a Nagios comment and optionally link to incident.

        Args:
            comment_data: Comment dictionary from parser
            incident: Optional incident to link comment to

        Returns:
            NagiosComment object if created, None otherwise
        """
        host_name = comment_data.get("host_name")
        service_description = comment_data.get("service_description")
        entry_time = comment_data.get("entry_time")
        author = comment_data.get("author", "unknown")
        comment_text = comment_data.get("comment_data", "")

        if not host_name or not entry_time:
            return None

        # Convert timestamp to datetime
        entry_datetime = datetime.fromtimestamp(entry_time)

        # Check if comment already exists
        existing = (
            self.session.query(NagiosComment)
            .filter(
                NagiosComment.host_name == host_name,
                NagiosComment.entry_time == entry_datetime,
                NagiosComment.author == author,
            )
            .first()
        )

        if existing:
            return existing

        # Create new Nagios comment
        nagios_comment = NagiosComment(
            incident_id=incident.id if incident else None,
            entry_time=entry_datetime,
            author=author,
            comment_data=comment_text,
            host_name=host_name,
            service_description=service_description,
        )
        self.session.add(nagios_comment)
        self.session.commit()
        return nagios_comment

    def link_comment_to_incident(
        self, comment: NagiosComment, incident: Incident
    ) -> None:
        """Link a Nagios comment to an incident if within timeframe.

        Args:
            comment: NagiosComment to link
            incident: Incident to link to
        """
        # Only link if comment was made during the incident
        if incident.started_at <= comment.entry_time:
            if incident.ended_at is None or comment.entry_time <= incident.ended_at:
                comment.incident_id = incident.id
                self.session.commit()

    def get_active_incidents(self) -> list[Incident]:
        """Get all active (unresolved) incidents.

        Returns:
            List of active Incident objects
        """
        return (
            self.session.query(Incident)
            .filter(Incident.ended_at.is_(None))
            .order_by(Incident.started_at.desc())
            .all()
        )

    def get_recent_incidents(self, hours: int = 24) -> list[Incident]:
        """Get incidents from the last N hours.

        Args:
            hours: Number of hours to look back

        Returns:
            List of Incident objects
        """
        cutoff = datetime.now().timestamp() - (hours * 3600)
        cutoff_datetime = datetime.fromtimestamp(cutoff)

        return (
            self.session.query(Incident)
            .filter(Incident.started_at >= cutoff_datetime)
            .order_by(Incident.started_at.desc())
            .all()
        )

    def cleanup_old_incidents(self, days: int) -> int:
        """Delete closed incidents older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of incidents deleted
        """
        cutoff = datetime.now().timestamp() - (days * 86400)
        cutoff_datetime = datetime.fromtimestamp(cutoff)

        deleted = (
            self.session.query(Incident)
            .filter(
                Incident.ended_at.isnot(None), Incident.ended_at < cutoff_datetime
            )
            .delete()
        )

        self.session.commit()
        return deleted

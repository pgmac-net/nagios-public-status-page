"""RSS feed generation for incidents."""

from datetime import timezone

from feedgen.feed import FeedGenerator
from sqlalchemy.orm import Session

from nagios_public_status_page.config import RSSConfig
from nagios_public_status_page.models import Incident


class IncidentFeedGenerator:
    """Generate RSS feeds for incidents."""

    def __init__(self, config: RSSConfig, base_url: str = "https://status.example.com"):
        """Initialize the feed generator.

        Args:
            config: RSS configuration
            base_url: Base URL for links in the feed
        """
        self.config = config
        self.base_url = base_url.rstrip("/")

    def _create_base_feed(self, title: str | None = None, description: str | None = None) -> FeedGenerator:
        """Create a base feed generator with common configuration.

        Args:
            title: Feed title (uses config default if not provided)
            description: Feed description (uses config default if not provided)

        Returns:
            Configured FeedGenerator instance
        """
        feed = FeedGenerator()
        feed.title(title or self.config.title)
        feed.description(description or self.config.description)
        feed.link(href=self.config.link, rel="alternate")
        feed.link(href=f"{self.base_url}/feed.rss", rel="self")
        feed.language("en")
        feed.generator("Nagios Public Status Page")
        return feed

    def _add_incident_to_feed(self, feed: FeedGenerator, incident: Incident) -> None:
        """Add an incident as a feed entry.

        Args:
            feed: FeedGenerator to add entry to
            incident: Incident to add
        """
        entry = feed.add_entry()

        # Build title
        if incident.incident_type == "host":
            title = f"{incident.host_name} - {incident.state}"
        else:
            title = f"{incident.host_name} / {incident.service_description} - {incident.state}"

        entry.title(title)

        # Build entry ID (unique identifier)
        entry_id = f"{self.base_url}/incidents/{incident.id}"
        entry.id(entry_id)
        entry.link(href=entry_id)

        # Set published date
        # Convert to UTC aware datetime
        pub_date = incident.started_at.replace(tzinfo=timezone.utc)
        entry.published(pub_date)

        # Set updated date
        if incident.ended_at:
            updated_date = incident.ended_at.replace(tzinfo=timezone.utc)
            entry.updated(updated_date)
        else:
            updated_date = (incident.last_check or incident.started_at).replace(tzinfo=timezone.utc)
            entry.updated(updated_date)

        # Build description
        description_parts = []

        # Status line
        status = "RESOLVED" if incident.ended_at else "ACTIVE"
        description_parts.append(f"<p><strong>Status:</strong> {status}</p>")

        # Start time
        description_parts.append(
            f"<p><strong>Started:</strong> {incident.started_at.strftime('%Y-%m-%d %H:%M:%S')}</p>"
        )

        # End time if resolved
        if incident.ended_at:
            description_parts.append(
                f"<p><strong>Ended:</strong> {incident.ended_at.strftime('%Y-%m-%d %H:%M:%S')}</p>"
            )

        # Plugin output
        if incident.plugin_output:
            description_parts.append(f"<p><strong>Details:</strong> {incident.plugin_output}</p>")

        # Comment count
        comment_count = len(incident.comments) + len(incident.nagios_comments)
        if comment_count > 0:
            description_parts.append(f"<p><strong>Comments:</strong> {comment_count}</p>")

        entry.description("".join(description_parts))

        # Set category based on incident type and state
        entry.category(term=incident.incident_type.upper(), label=incident.incident_type.title())
        entry.category(term=incident.state, label=incident.state)

    def generate_global_feed(self, session: Session, hours: int = 24) -> str:
        """Generate RSS feed for all recent incidents.

        Args:
            session: Database session
            hours: Number of hours to look back

        Returns:
            RSS feed XML string
        """
        from nagios_public_status_page.collector.incident_tracker import IncidentTracker

        feed = self._create_base_feed()

        # Get recent incidents
        tracker = IncidentTracker(session)
        incidents = tracker.get_recent_incidents(hours=hours)

        # Limit to max_items
        incidents = incidents[: self.config.max_items]

        # Add each incident as a feed entry
        for incident in incidents:
            self._add_incident_to_feed(feed, incident)

        return feed.rss_str(pretty=True).decode("utf-8")

    def generate_host_feed(self, session: Session, host_name: str, hours: int = 24) -> str | None:
        """Generate RSS feed for a specific host's incidents.

        Args:
            session: Database session
            host_name: Host name to filter by
            hours: Number of hours to look back

        Returns:
            RSS feed XML string, or None if host has no incidents
        """
        from nagios_public_status_page.collector.incident_tracker import IncidentTracker

        feed = self._create_base_feed(
            title=f"{self.config.title} - {host_name}",
            description=f"Status updates for {host_name}",
        )

        # Get recent incidents for this host
        tracker = IncidentTracker(session)
        incidents = tracker.get_recent_incidents(hours=hours)

        # Filter by host
        incidents = [inc for inc in incidents if inc.host_name == host_name]

        if not incidents:
            return None

        # Limit to max_items
        incidents = incidents[: self.config.max_items]

        # Add each incident as a feed entry
        for incident in incidents:
            self._add_incident_to_feed(feed, incident)

        return feed.rss_str(pretty=True).decode("utf-8")

    def generate_service_feed(
        self, session: Session, host_name: str, service_description: str, hours: int = 24
    ) -> str | None:
        """Generate RSS feed for a specific service's incidents.

        Args:
            session: Database session
            host_name: Host name
            service_description: Service description
            hours: Number of hours to look back

        Returns:
            RSS feed XML string, or None if service has no incidents
        """
        from nagios_public_status_page.collector.incident_tracker import IncidentTracker

        feed = self._create_base_feed(
            title=f"{self.config.title} - {host_name}/{service_description}",
            description=f"Status updates for {host_name}/{service_description}",
        )

        # Get recent incidents for this service
        tracker = IncidentTracker(session)
        incidents = tracker.get_recent_incidents(hours=hours)

        # Filter by host and service
        incidents = [
            inc
            for inc in incidents
            if inc.host_name == host_name
            and inc.service_description == service_description
            and inc.incident_type == "service"
        ]

        if not incidents:
            return None

        # Limit to max_items
        incidents = incidents[: self.config.max_items]

        # Add each incident as a feed entry
        for incident in incidents:
            self._add_incident_to_feed(feed, incident)

        return feed.rss_str(pretty=True).decode("utf-8")

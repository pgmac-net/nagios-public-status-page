"""FastAPI routes for the status page API."""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from status_page.api.schemas import (
    CommentCreate,
    CommentResponse,
    HealthResponse,
    HostStatusResponse,
    IncidentResponse,
    IncidentWithComments,
    PostIncidentReviewUpdate,
    ServiceStatusResponse,
    StatusSummary,
)
from status_page.collector.incident_tracker import IncidentTracker
from status_page.db.database import get_session
from status_page.models import Comment, Incident

router = APIRouter(prefix="/api", tags=["api"])
rss_router = APIRouter(prefix="/feed", tags=["rss"])


def get_db() -> Session:
    """Dependency to get database session.

    Yields:
        Database session
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


@router.get("/health", response_model=HealthResponse)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Health check endpoint.

    Args:
        db: Database session

    Returns:
        Health status information
    """
    from status_page.collector.poller import StatusPoller
    from status_page.config import load_config

    try:
        config = load_config()
        poller = StatusPoller(config)

        # Get last poll metadata
        last_poll = poller.get_last_poll()
        is_stale = poller.is_data_stale()

        # Get active incidents count
        tracker = IncidentTracker(db)
        active_count = len(tracker.get_active_incidents())

        # Calculate status.dat age
        age_seconds = None
        if last_poll and last_poll.status_dat_mtime:
            age_seconds = (datetime.now() - last_poll.status_dat_mtime).total_seconds()

        status = "healthy"
        if is_stale:
            status = "stale"
        if active_count > 0:
            status = "degraded"

        return HealthResponse(
            status=status,
            last_poll_time=last_poll.last_poll_time if last_poll else None,
            status_dat_age_seconds=age_seconds,
            data_is_stale=is_stale,
            active_incidents_count=active_count,
            database_accessible=True,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Health check failed: {exc}") from exc


@router.get("/status", response_model=StatusSummary)
def get_status(db: Session = Depends(get_db)) -> StatusSummary:
    """Get overall status summary.

    Args:
        db: Database session

    Returns:
        Status summary with host/service counts
    """
    from status_page.collector.poller import StatusPoller
    from status_page.config import load_config
    from status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        # Get hosts and services
        hosts = parser.get_hosts(hostgroups=config.nagios.hostgroups)
        services = parser.get_services(servicegroups=config.nagios.servicegroups)

        # Count host states
        hosts_up = sum(1 for h in hosts if h.get("current_state") == 0)
        hosts_down = sum(1 for h in hosts if h.get("current_state") == 1)
        hosts_unreachable = sum(1 for h in hosts if h.get("current_state") == 2)

        # Count service states
        services_ok = sum(1 for s in services if s.get("current_state") == 0)
        services_warning = sum(1 for s in services if s.get("current_state") == 1)
        services_critical = sum(1 for s in services if s.get("current_state") == 2)
        services_unknown = sum(1 for s in services if s.get("current_state") == 3)

        # Get active incidents
        tracker = IncidentTracker(db)
        active_incidents = len(tracker.get_active_incidents())

        # Get last poll time
        poller = StatusPoller(config)
        last_poll = poller.get_last_poll()
        is_stale = poller.is_data_stale()

        return StatusSummary(
            total_hosts=len(hosts),
            hosts_up=hosts_up,
            hosts_down=hosts_down,
            hosts_unreachable=hosts_unreachable,
            total_services=len(services),
            services_ok=services_ok,
            services_warning=services_warning,
            services_critical=services_critical,
            services_unknown=services_unknown,
            active_incidents=active_incidents,
            last_poll=last_poll.last_poll_time if last_poll else None,
            data_is_stale=is_stale,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get status: {exc}") from exc


@router.get("/hosts", response_model=list[HostStatusResponse])
def get_hosts(db: Session = Depends(get_db)) -> list[HostStatusResponse]:
    """Get all monitored hosts with their current status.

    Args:
        db: Database session

    Returns:
        List of host statuses
    """
    from status_page.config import load_config
    from status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        hosts = parser.get_hosts(hostgroups=config.nagios.hostgroups)

        state_names = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}

        return [
            HostStatusResponse(
                host_name=h.get("host_name", ""),
                current_state=h.get("current_state", 0),
                state_name=state_names.get(h.get("current_state", 0), "UNKNOWN"),
                plugin_output=h.get("plugin_output"),
                last_check=datetime.fromtimestamp(h["last_check"]) if h.get("last_check") else None,
                is_problem=h.get("current_state", 0) in {1, 2},
            )
            for h in hosts
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get hosts: {exc}") from exc


@router.get("/services", response_model=list[ServiceStatusResponse])
def get_services(db: Session = Depends(get_db)) -> list[ServiceStatusResponse]:
    """Get all monitored services with their current status.

    Args:
        db: Database session

    Returns:
        List of service statuses
    """
    from status_page.config import load_config
    from status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        services = parser.get_services(servicegroups=config.nagios.servicegroups)

        state_names = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}

        return [
            ServiceStatusResponse(
                host_name=s.get("host_name", ""),
                service_description=s.get("service_description", ""),
                current_state=s.get("current_state", 0),
                state_name=state_names.get(s.get("current_state", 0), "UNKNOWN"),
                plugin_output=s.get("plugin_output"),
                last_check=datetime.fromtimestamp(s["last_check"]) if s.get("last_check") else None,
                is_problem=s.get("current_state", 0) in {1, 2, 3},
            )
            for s in services
        ]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get services: {exc}") from exc


@router.get("/incidents", response_model=list[IncidentResponse])
def get_incidents(
    active_only: bool = False,
    hours: int = 24,
    db: Session = Depends(get_db),
) -> list[IncidentResponse]:
    """Get incidents, optionally filtered.

    Args:
        active_only: If True, return only active incidents
        hours: Number of hours to look back (if not active_only)
        db: Database session

    Returns:
        List of incidents
    """
    try:
        tracker = IncidentTracker(db)

        if active_only:
            incidents = tracker.get_active_incidents()
        else:
            incidents = tracker.get_recent_incidents(hours=hours)

        return [IncidentResponse.model_validate(inc) for inc in incidents]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to get incidents: {exc}") from exc


@router.get("/incidents/{incident_id}", response_model=IncidentWithComments)
def get_incident(incident_id: int, db: Session = Depends(get_db)) -> IncidentWithComments:
    """Get a specific incident with all its comments.

    Args:
        incident_id: Incident ID
        db: Database session

    Returns:
        Incident with comments

    Raises:
        HTTPException: If incident not found
    """
    try:
        incident = db.query(Incident).filter(Incident.id == incident_id).first()

        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        return IncidentWithComments(
            incident=IncidentResponse.model_validate(incident),
            comments=[CommentResponse.model_validate(c) for c in incident.comments],
            nagios_comments=[CommentResponse.model_validate(c) for c in incident.nagios_comments],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get incident: {exc}"
        ) from exc


@router.post("/incidents/{incident_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(
    incident_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
) -> CommentResponse:
    """Add a comment to an incident.

    Args:
        incident_id: Incident ID
        comment: Comment data
        db: Database session

    Returns:
        Created comment

    Raises:
        HTTPException: If incident not found
    """
    try:
        # Check if incident exists
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Create comment
        new_comment = Comment(
            incident_id=incident_id,
            author=comment.author,
            comment_text=comment.comment_text,
            created_at=datetime.now(),
        )
        db.add(new_comment)
        db.commit()
        db.refresh(new_comment)

        return CommentResponse.model_validate(new_comment)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to add comment: {exc}"
        ) from exc


@router.patch("/incidents/{incident_id}/pir", response_model=IncidentResponse)
def update_pir_url(
    incident_id: int,
    pir_data: PostIncidentReviewUpdate,
    db: Session = Depends(get_db),
) -> IncidentResponse:
    """Update the post-incident review URL for an incident.

    Args:
        incident_id: Incident ID
        pir_data: Post-incident review URL data
        db: Database session

    Returns:
        Updated incident

    Raises:
        HTTPException: If incident not found
    """
    try:
        # Find incident
        incident = db.query(Incident).filter(Incident.id == incident_id).first()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")

        # Update PIR URL
        incident.post_incident_review_url = pir_data.post_incident_review_url
        db.commit()
        db.refresh(incident)

        return IncidentResponse.model_validate(incident)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"Failed to update PIR URL: {exc}"
        ) from exc


# RSS Feed Endpoints


@rss_router.get("/rss")
def get_global_rss_feed(hours: int = 24, db: Session = Depends(get_db)) -> Response:
    """Get RSS feed for all recent incidents.

    Args:
        hours: Number of hours to look back (default 24)
        db: Database session

    Returns:
        RSS feed XML
    """
    from status_page.config import load_config
    from status_page.rss.feed_generator import IncidentFeedGenerator

    try:
        config = load_config()
        generator = IncidentFeedGenerator(config.rss, base_url=config.rss.link)
        feed_xml = generator.generate_global_feed(db, hours=hours)

        return Response(content=feed_xml, media_type="application/rss+xml")
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate RSS feed: {exc}"
        ) from exc


@rss_router.get("/host/{host_name}/rss")
def get_host_rss_feed(
    host_name: str, hours: int = 24, db: Session = Depends(get_db)
) -> Response:
    """Get RSS feed for a specific host's incidents.

    Args:
        host_name: Host name to filter by
        hours: Number of hours to look back (default 24)
        db: Database session

    Returns:
        RSS feed XML

    Raises:
        HTTPException: If host has no incidents
    """
    from status_page.config import load_config
    from status_page.rss.feed_generator import IncidentFeedGenerator

    try:
        config = load_config()
        generator = IncidentFeedGenerator(config.rss, base_url=config.rss.link)
        feed_xml = generator.generate_host_feed(db, host_name, hours=hours)

        if feed_xml is None:
            raise HTTPException(
                status_code=404, detail=f"No incidents found for host: {host_name}"
            )

        return Response(content=feed_xml, media_type="application/rss+xml")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate RSS feed: {exc}"
        ) from exc


@rss_router.get("/service/{host_name}/{service_description}/rss")
def get_service_rss_feed(
    host_name: str,
    service_description: str,
    hours: int = 24,
    db: Session = Depends(get_db),
) -> Response:
    """Get RSS feed for a specific service's incidents.

    Args:
        host_name: Host name
        service_description: Service description
        hours: Number of hours to look back (default 24)
        db: Database session

    Returns:
        RSS feed XML

    Raises:
        HTTPException: If service has no incidents
    """
    from status_page.config import load_config
    from status_page.rss.feed_generator import IncidentFeedGenerator

    try:
        config = load_config()
        generator = IncidentFeedGenerator(config.rss, base_url=config.rss.link)
        feed_xml = generator.generate_service_feed(
            db, host_name, service_description, hours=hours
        )

        if feed_xml is None:
            raise HTTPException(
                status_code=404,
                detail=f"No incidents found for service: {host_name}/{service_description}",
            )

        return Response(content=feed_xml, media_type="application/rss+xml")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate RSS feed: {exc}"
        ) from exc

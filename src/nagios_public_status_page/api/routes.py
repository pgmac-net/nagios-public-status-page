"""FastAPI routes for the status page API."""

import secrets
from collections.abc import Generator
from datetime import datetime
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from sqlalchemy.orm import Session

from nagios_public_status_page.api.schemas import (
    CommentCreate,
    CommentResponse,
    HealthResponse,
    HostStatusResponse,
    IncidentResponse,
    IncidentWithComments,
    NagiosCommentResponse,
    PostIncidentReviewUpdate,
    SchedulerStatusResponse,
    ServiceStatusResponse,
    StatusSummary,
)
from nagios_public_status_page.collector.incident_tracker import IncidentTracker
from nagios_public_status_page.db.database import get_session
from nagios_public_status_page.models import Comment, Incident

router = APIRouter(prefix="/api", tags=["api"])
rss_router = APIRouter(prefix="/feed", tags=["rss"])

security = HTTPBasic()


def get_db() -> Generator[Session, None, None]:
    """Dependency to get database session.

    Yields:
        Database session
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def verify_write_access(credentials: HTTPBasicCredentials = Depends(security)) -> None:
    """Verify Basic Auth credentials for write operations.

    Args:
        credentials: HTTP Basic Auth credentials

    Raises:
        HTTPException: If authentication is required but credentials are invalid
    """
    from nagios_public_status_page.config import load_config

    config = load_config()

    # If no auth configured, allow all access
    if not config.api.basic_auth_username or not config.api.basic_auth_password:
        return

    # Verify credentials using constant-time comparison to prevent timing attacks
    correct_username = secrets.compare_digest(
        credentials.username.encode("utf8"),
        config.api.basic_auth_username.encode("utf8")
    )
    correct_password = secrets.compare_digest(
        credentials.password.encode("utf8"),
        config.api.basic_auth_password.encode("utf8")
    )

    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="""
    Check the overall health of the API and monitoring system.

    Returns information about:
    - API operational status
    - Last poll time and data freshness
    - Active incident count
    - Database connectivity
    - Scheduler health and self-healing status

    **Status Values:**
    - `healthy`: System operating normally
    - `degraded`: Active incidents present
    - `stale`: Data has not been updated recently

    **Scheduler Health Status:**
    - `healthy`: Scheduler running normally with no failures
    - `degraded`: Scheduler running but experiencing some failures
    - `critical`: Scheduler not running or exceeded failure threshold
    """,
    responses={
        200: {
            "description": "Health check successful",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "last_poll_time": "2025-01-12T10:30:00",
                        "status_dat_age_seconds": 45.2,
                        "data_is_stale": False,
                        "active_incidents_count": 0,
                        "database_accessible": True,
                        "scheduler_status": {
                            "is_running": True,
                            "scheduler_running": True,
                            "consecutive_failures": 0,
                            "max_consecutive_failures": 3,
                            "recovery_attempts": 0,
                            "last_recovery_time": None,
                            "health_status": "healthy"
                        }
                    }
                }
            }
        }
    }
)
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """Health check endpoint.

    Args:
        db: Database session

    Returns:
        Health status information
    """
    from nagios_public_status_page.collector.poller import StatusPoller
    from nagios_public_status_page.config import load_config

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

        # Get scheduler status
        scheduler_status_dict = poller.get_scheduler_status()
        scheduler_status = SchedulerStatusResponse(**scheduler_status_dict)

        poll_time = cast(datetime, last_poll.last_poll_time) if last_poll else None
        return HealthResponse(
            status=status,
            last_poll_time=poll_time,
            status_dat_age_seconds=age_seconds,
            data_is_stale=is_stale,
            active_incidents_count=active_count,
            database_accessible=True,
            scheduler_status=scheduler_status,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Health check failed: {exc}") from exc


@router.post("/poll")
def trigger_poll(
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_write_access)
) -> dict:
    """Manually trigger a status.dat poll.

    Args:
        db: Database session

    Returns:
        Poll results and statistics
    """
    from nagios_public_status_page.collector.poller import StatusPoller
    from nagios_public_status_page.config import load_config

    try:
        config = load_config()
        poller = StatusPoller(config)
        results = poller.poll()

        return {
            "success": True,
            "message": "Poll completed successfully",
            "results": results,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Poll failed: {exc}") from exc


@router.get(
    "/status",
    response_model=StatusSummary,
    summary="Overall Status Summary",
    description="""
    Get a comprehensive summary of all monitored hosts and services.

    Returns aggregated counts for:
    - Host states (UP, DOWN, UNREACHABLE)
    - Service states (OK, WARNING, CRITICAL, UNKNOWN)
    - Active incidents
    - Last poll timestamp

    This endpoint is ideal for dashboard displays and high-level monitoring.
    """,
    responses={
        200: {
            "description": "Status summary retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "total_hosts": 10,
                        "hosts_up": 9,
                        "hosts_down": 1,
                        "hosts_unreachable": 0,
                        "total_services": 50,
                        "services_ok": 45,
                        "services_warning": 3,
                        "services_critical": 2,
                        "services_unknown": 0,
                        "active_incidents": 2,
                        "last_poll": "2025-01-12T10:30:00",
                        "data_is_stale": False
                    }
                }
            }
        }
    }
)
def get_status(db: Session = Depends(get_db)) -> StatusSummary:
    """Get overall status summary.

    Args:
        db: Database session

    Returns:
        Status summary with host/service counts
    """
    from nagios_public_status_page.collector.poller import StatusPoller
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        # Get hosts and services
        explicit_hosts = config.nagios.hosts if config.nagios.hosts else None
        explicit_services = None
        if config.nagios.services:
            explicit_services = [
                (svc.host_name, svc.service_description)
                for svc in config.nagios.services
            ]

        hosts = parser.get_hosts(
            hostgroups=config.nagios.hostgroups if config.nagios.hostgroups else None,
            explicit_hosts=explicit_hosts,
        )
        services = parser.get_services(
            servicegroups=config.nagios.servicegroups if config.nagios.servicegroups else None,
            explicit_services=explicit_services,
        )

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

        poll_time = cast(datetime, last_poll.last_poll_time) if last_poll else None
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
            last_poll=poll_time,
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
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        explicit_hosts = config.nagios.hosts if config.nagios.hosts else None
        hosts = parser.get_hosts(
            hostgroups=config.nagios.hostgroups if config.nagios.hostgroups else None,
            explicit_hosts=explicit_hosts,
        )

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
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.parser.status_dat import StatusDatParser

    try:
        config = load_config()
        parser = StatusDatParser(config.nagios.status_dat_path)
        parser.parse()

        explicit_services = None
        if config.nagios.services:
            explicit_services = [
                (svc.host_name, svc.service_description)
                for svc in config.nagios.services
            ]

        services = parser.get_services(
            servicegroups=config.nagios.servicegroups if config.nagios.servicegroups else None,
            explicit_services=explicit_services,
        )

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


@router.get(
    "/incidents",
    response_model=list[IncidentResponse],
    summary="List Incidents",
    description="""
    Retrieve a list of incidents with optional filtering.

    **Query Parameters:**
    - `active_only`: Set to `true` to return only ongoing incidents
    - `hours`: Number of hours to look back (default: 24, ignored if active_only=true)

    **Incident Types:**
    - `host`: Host is DOWN or UNREACHABLE
    - `service`: Service is WARNING, CRITICAL, or UNKNOWN

    Incidents are automatically created when problems are detected and closed when resolved.
    """,
    responses={
        200: {
            "description": "List of incidents retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": 123,
                            "incident_type": "service",
                            "host_name": "web-server-01",
                            "service_description": "HTTPS",
                            "state": "CRITICAL",
                            "started_at": "2025-01-12T09:15:00",
                            "ended_at": None,
                            "last_check": "2025-01-12T10:30:00",
                            "plugin_output": "Connection refused",
                            "post_incident_review_url": None,
                            "acknowledged": False,
                            "is_active": True
                        }
                    ]
                }
            }
        }
    }
)
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
            nagios_comments=[
                NagiosCommentResponse.model_validate(c) for c in incident.nagios_comments
            ],
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to get incident: {exc}"
        ) from exc


@router.post(
    "/incidents/{incident_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add Comment to Incident",
    description="""
    Add a comment to an existing incident.

    **Authentication Required**: This endpoint requires HTTP Basic Authentication.

    Use this to provide updates during an incident, coordinate response efforts,
    or document resolution steps.

    **Request Body:**
    - `author`: Name of the person adding the comment
    - `comment_text`: The comment content (supports plain text)
    """,
    responses={
        201: {
            "description": "Comment created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": 456,
                        "incident_id": 123,
                        "author": "Jane Smith",
                        "comment_text": "Database failover completed successfully",
                        "created_at": "2025-01-12T10:45:00"
                    }
                }
            }
        },
        401: {"description": "Authentication required or invalid credentials"},
        404: {"description": "Incident not found"}
    }
)
def add_comment(
    incident_id: int,
    comment: CommentCreate,
    db: Session = Depends(get_db),
    _auth: None = Depends(verify_write_access)
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
    _auth: None = Depends(verify_write_access)
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


@rss_router.get(
    "/rss.xml",
    summary="Global RSS Feed",
    description="""
    Subscribe to an RSS feed of all recent incidents.

    **Query Parameters:**
    - `hours`: Number of hours to look back (default: 24)

    Use this feed to get real-time notifications about all incidents
    in your RSS reader or automation tools.

    **Content-Type:** `application/rss+xml`
    """,
    responses={
        200: {
            "description": "RSS feed generated successfully",
            "content": {
                "application/rss+xml": {
                    "example": '<?xml version="1.0" encoding="utf-8"?><rss version="2.0">...</rss>'
                }
            }
        }
    }
)
def get_global_rss_feed(hours: int = 24, db: Session = Depends(get_db)) -> Response:
    """Get RSS feed for all recent incidents.

    Args:
        hours: Number of hours to look back (default 24)
        db: Database session

    Returns:
        RSS feed XML
    """
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.rss.feed_generator import IncidentFeedGenerator

    try:
        config = load_config()
        generator = IncidentFeedGenerator(config.rss, base_url=config.rss.link)
        feed_xml = generator.generate_global_feed(db, hours=hours)

        return Response(content=feed_xml, media_type="application/rss+xml")
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to generate RSS feed: {exc}"
        ) from exc


@rss_router.get("/host/{host_name}/rss.xml")
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
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.rss.feed_generator import IncidentFeedGenerator

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


@rss_router.get("/service/{host_name}/{service_description}/rss.xml")
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
    from nagios_public_status_page.config import load_config
    from nagios_public_status_page.rss.feed_generator import IncidentFeedGenerator

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

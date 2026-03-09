"""Pydantic schemas for API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IncidentResponse(BaseModel):
    """Schema for incident response.

    Represents a monitoring incident (host or service problem).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "incident_type": "service",
                "host_name": "web-server-01",
                "service_description": "HTTPS",
                "state": "CRITICAL",
                "started_at": "2025-01-12T09:15:00",
                "ended_at": None,
                "last_check": "2025-01-12T10:30:00",
                "plugin_output": "Connection refused on port 443",
                "post_incident_review_url": "https://example.com/pir/123",
                "acknowledged": False,
                "is_active": True
            }
        }
    )

    id: int = Field(description="Unique incident identifier")
    incident_type: str = Field(description="Type of incident: 'host' or 'service'")
    host_name: str = Field(description="Name of the affected host")
    service_description: str | None = Field(
        default=None,
        description="Service name (null for host incidents)"
    )
    state: str = Field(
        description="Current state: UP/DOWN/UNREACHABLE for hosts, OK/WARNING/CRITICAL/UNKNOWN for services"
    )
    started_at: datetime = Field(description="When the incident started")
    ended_at: datetime | None = Field(
        default=None,
        description="When the incident ended (null if still active)"
    )
    last_check: datetime | None = Field(
        default=None,
        description="Last time this was checked by Nagios"
    )
    plugin_output: str | None = Field(
        default=None,
        description="Output from the monitoring plugin"
    )
    post_incident_review_url: str | None = Field(
        default=None,
        description="URL to post-incident review document"
    )
    acknowledged: bool = Field(description="Whether the incident has been acknowledged in Nagios")
    is_active: bool = Field(description="Whether the incident is currently ongoing")


class CommentResponse(BaseModel):
    """Schema for comment response.

    Represents a user comment on an incident.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 456,
                "incident_id": 123,
                "author": "Jane Smith",
                "comment_text": "Database failover completed successfully",
                "created_at": "2025-01-12T10:45:00"
            }
        }
    )

    id: int = Field(description="Unique comment identifier")
    incident_id: int = Field(description="ID of the incident this comment belongs to")
    author: str = Field(description="Name of the comment author")
    comment_text: str = Field(description="The comment content")
    created_at: datetime = Field(description="When the comment was created")


class CommentCreate(BaseModel):
    """Schema for creating a comment.

    Use this to add updates or notes to an incident.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "author": "John Doe",
                "comment_text": "Restarted the service, monitoring for stability"
            }
        }
    )

    author: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Your name or identifier"
    )
    comment_text: str = Field(
        ...,
        min_length=1,
        description="The comment text"
    )


class PostIncidentReviewUpdate(BaseModel):
    """Schema for updating post-incident review URL."""

    post_incident_review_url: str = Field(..., min_length=1, max_length=512)


class NagiosCommentResponse(BaseModel):
    """Schema for Nagios comment response."""

    id: int
    incident_id: int | None
    entry_time: datetime
    author: str
    comment_data: str
    host_name: str
    service_description: str | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class HostStatusResponse(BaseModel):
    """Schema for host status response."""

    host_name: str
    current_state: int
    state_name: str
    plugin_output: str | None
    last_check: datetime | None
    is_problem: bool


class ServiceStatusResponse(BaseModel):
    """Schema for service status response."""

    host_name: str
    service_description: str
    current_state: int
    state_name: str
    plugin_output: str | None
    last_check: datetime | None
    is_problem: bool


class StatusSummary(BaseModel):
    """Schema for overall status summary.

    Provides aggregated counts of all monitored resources.
    """

    model_config = ConfigDict(
        json_schema_extra={
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
    )

    total_hosts: int = Field(description="Total number of monitored hosts")
    hosts_up: int = Field(description="Number of hosts in UP state")
    hosts_down: int = Field(description="Number of hosts in DOWN state")
    hosts_unreachable: int = Field(description="Number of hosts in UNREACHABLE state")
    total_services: int = Field(description="Total number of monitored services")
    services_ok: int = Field(description="Number of services in OK state")
    services_warning: int = Field(description="Number of services in WARNING state")
    services_critical: int = Field(description="Number of services in CRITICAL state")
    services_unknown: int = Field(description="Number of services in UNKNOWN state")
    active_incidents: int = Field(description="Number of currently active incidents")
    last_poll: datetime | None = Field(
        default=None,
        description="Timestamp of last successful poll"
    )
    data_is_stale: bool = Field(
        description="Whether data has not been updated within the expected interval"
    )


class SchedulerStatusResponse(BaseModel):
    """Schema for scheduler health status.

    Provides detailed information about the poller scheduler state.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "is_running": True,
                "scheduler_running": True,
                "consecutive_failures": 0,
                "max_consecutive_failures": 3,
                "recovery_attempts": 0,
                "last_recovery_time": None,
                "health_status": "healthy"
            }
        }
    )

    is_running: bool = Field(description="Whether the poller is marked as running")
    scheduler_running: bool = Field(description="Whether the APScheduler thread is running")
    consecutive_failures: int = Field(description="Current count of consecutive poll failures")
    max_consecutive_failures: int = Field(
        description="Threshold for triggering automatic recovery"
    )
    recovery_attempts: int = Field(description="Total number of recovery attempts")
    last_recovery_time: str | None = Field(
        default=None,
        description="ISO timestamp of last recovery attempt"
    )
    health_status: str = Field(
        description="Overall scheduler health: 'healthy', 'degraded', or 'critical'"
    )


class HealthResponse(BaseModel):
    """Schema for health check response.

    Provides system health and operational status.
    """

    model_config = ConfigDict(
        json_schema_extra={
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
    )

    status: str = Field(
        description="Overall health status: 'healthy', 'degraded', or 'stale'"
    )
    last_poll_time: datetime | None = Field(
        default=None,
        description="When the last poll was completed"
    )
    status_dat_age_seconds: float | None = Field(
        default=None,
        description="Age of the Nagios status.dat file in seconds"
    )
    data_is_stale: bool = Field(
        description="Whether data has not been updated within the expected interval"
    )
    active_incidents_count: int = Field(description="Number of active incidents")
    database_accessible: bool = Field(description="Whether database is accessible")
    scheduler_status: SchedulerStatusResponse | None = Field(
        default=None,
        description="Scheduler health information including failure tracking and recovery status"
    )


class PollMetadataResponse(BaseModel):
    """Schema for poll metadata response."""

    id: int
    last_poll_time: datetime
    status_dat_mtime: datetime
    records_processed: int | None

    class Config:
        """Pydantic config."""

        from_attributes = True


class IncidentWithComments(BaseModel):
    """Schema for incident with all comments."""

    incident: IncidentResponse
    comments: list[CommentResponse]
    nagios_comments: list[NagiosCommentResponse]

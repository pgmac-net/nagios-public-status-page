"""Pydantic schemas for API requests and responses."""

from datetime import datetime

from pydantic import BaseModel, Field


class IncidentResponse(BaseModel):
    """Schema for incident response."""

    id: int
    incident_type: str
    host_name: str
    service_description: str | None
    state: str
    started_at: datetime
    ended_at: datetime | None
    last_check: datetime | None
    plugin_output: str | None
    post_incident_review_url: str | None
    acknowledged: bool
    is_active: bool

    class Config:
        """Pydantic config."""

        from_attributes = True


class CommentResponse(BaseModel):
    """Schema for comment response."""

    id: int
    incident_id: int
    author: str
    comment_text: str
    created_at: datetime

    class Config:
        """Pydantic config."""

        from_attributes = True


class CommentCreate(BaseModel):
    """Schema for creating a comment."""

    author: str = Field(..., min_length=1, max_length=255)
    comment_text: str = Field(..., min_length=1)


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
    """Schema for overall status summary."""

    total_hosts: int
    hosts_up: int
    hosts_down: int
    hosts_unreachable: int
    total_services: int
    services_ok: int
    services_warning: int
    services_critical: int
    services_unknown: int
    active_incidents: int
    last_poll: datetime | None
    data_is_stale: bool


class HealthResponse(BaseModel):
    """Schema for health check response."""

    status: str
    last_poll_time: datetime | None
    status_dat_age_seconds: float | None
    data_is_stale: bool
    active_incidents_count: int
    database_accessible: bool


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

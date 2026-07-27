"""Database models for the status page application."""

from datetime import UTC, datetime

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from nagios_public_status_page.db.types import UTCDateTime


def _naive_isoformat(value: datetime | None) -> str | None:
    """Render a UTC timestamp without an offset.

    Mirrors the JSON API contract, which serialises timestamps as naive strings
    that consumers interpret as UTC. See docs/UTC_TIMESTAMPS.md.

    Args:
        value: An aware UTC datetime, or None

    Returns:
        ISO 8601 string with no offset, or None
    """
    if value is None:
        return None
    return value.replace(tzinfo=None).isoformat()


class Base(DeclarativeBase):
    pass


class Incident(Base):
    """Track host and service incidents (problems)."""

    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_type: Mapped[str] = mapped_column(String(20))
    host_name: Mapped[str] = mapped_column(String(255), index=True)
    service_description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str] = mapped_column(String(20))
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    ended_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True, index=True)
    last_check: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    plugin_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_incident_review_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    acknowledged: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    comments: Mapped[list["Comment"]] = relationship("Comment", back_populates="incident", cascade="all, delete-orphan")
    nagios_comments: Mapped[list["NagiosComment"]] = relationship("NagiosComment", back_populates="incident", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        """Return string representation."""
        if self.incident_type == "service":
            return f"<Incident {self.host_name}/{self.service_description} {self.state}>"
        return f"<Incident {self.host_name} {self.state}>"

    @property
    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.ended_at is None

    def to_dict(self) -> dict:
        """Convert incident to dictionary."""
        return {
            "id": self.id,
            "incident_type": self.incident_type,
            "host_name": self.host_name,
            "service_description": self.service_description,
            "state": self.state,
            "started_at": _naive_isoformat(self.started_at),
            "ended_at": _naive_isoformat(self.ended_at),
            "last_check": _naive_isoformat(self.last_check),
            "plugin_output": self.plugin_output,
            "post_incident_review_url": self.post_incident_review_url,
            "acknowledged": bool(self.acknowledged),
            "is_active": self.is_active,
        }


class Comment(Base):
    """Manual status updates and comments."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int] = mapped_column(Integer, ForeignKey("incidents.id"), index=True)
    author: Mapped[str] = mapped_column(String(255))
    comment_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=lambda: datetime.now(UTC), index=True
    )

    # Relationships
    incident: Mapped["Incident"] = relationship("Incident", back_populates="comments")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<Comment {self.id} by {self.author}>"

    def to_dict(self) -> dict:
        """Convert comment to dictionary."""
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "author": self.author,
            "comment_text": self.comment_text,
            "created_at": _naive_isoformat(self.created_at),
        }


class NagiosComment(Base):
    """Comments pulled from Nagios status.dat."""

    __tablename__ = "nagios_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("incidents.id"), nullable=True, index=True)
    entry_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    author: Mapped[str] = mapped_column(String(255))
    comment_data: Mapped[str] = mapped_column(Text)
    host_name: Mapped[str] = mapped_column(String(255), index=True)
    service_description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    incident: Mapped["Incident | None"] = relationship("Incident", back_populates="nagios_comments")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<NagiosComment {self.id} on {self.host_name}>"

    def to_dict(self) -> dict:
        """Convert Nagios comment to dictionary."""
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "entry_time": _naive_isoformat(self.entry_time),
            "author": self.author,
            "comment_data": self.comment_data,
            "host_name": self.host_name,
            "service_description": self.service_description,
        }


class PollMetadata(Base):
    """Track polling metadata and history."""

    __tablename__ = "poll_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_poll_time: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    status_dat_mtime: Mapped[datetime] = mapped_column(UTCDateTime)
    records_processed: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<PollMetadata {self.last_poll_time}>"

    def to_dict(self) -> dict:
        """Convert poll metadata to dictionary."""
        return {
            "id": self.id,
            "last_poll_time": _naive_isoformat(self.last_poll_time),
            "status_dat_mtime": _naive_isoformat(self.status_dat_mtime),
            "records_processed": self.records_processed,
        }

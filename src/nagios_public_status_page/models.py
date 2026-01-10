"""Database models for the status page application."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Incident(Base):
    """Track host and service incidents (problems)."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True)
    incident_type = Column(String(20), nullable=False)  # 'host' or 'service'
    host_name = Column(String(255), nullable=False, index=True)
    service_description = Column(String(255), nullable=True)  # NULL for host incidents
    state = Column(String(20), nullable=False)  # WARNING, CRITICAL, DOWN, etc.
    started_at = Column(DateTime, nullable=False, index=True)
    ended_at = Column(DateTime, nullable=True, index=True)
    last_check = Column(DateTime, nullable=True)
    plugin_output = Column(Text, nullable=True)
    post_incident_review_url = Column(String(512), nullable=True)  # Link to PIR document
    acknowledged = Column(Integer, default=0, nullable=False)  # 0=not acked, 1=acked

    # Relationships
    comments = relationship("Comment", back_populates="incident", cascade="all, delete-orphan")
    nagios_comments = relationship("NagiosComment", back_populates="incident", cascade="all, delete-orphan")

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
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "last_check": self.last_check.isoformat() if self.last_check else None,
            "plugin_output": self.plugin_output,
            "post_incident_review_url": self.post_incident_review_url,
            "acknowledged": bool(self.acknowledged),
            "is_active": self.is_active,
        }


class Comment(Base):
    """Manual status updates and comments."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=False, index=True)
    author = Column(String(255), nullable=False)
    comment_text = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    # Relationships
    incident = relationship("Incident", back_populates="comments")

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
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class NagiosComment(Base):
    """Comments pulled from Nagios status.dat."""

    __tablename__ = "nagios_comments"

    id = Column(Integer, primary_key=True)
    incident_id = Column(Integer, ForeignKey("incidents.id"), nullable=True, index=True)
    entry_time = Column(DateTime, nullable=False, index=True)
    author = Column(String(255), nullable=False)
    comment_data = Column(Text, nullable=False)
    host_name = Column(String(255), nullable=False, index=True)
    service_description = Column(String(255), nullable=True)

    # Relationships
    incident = relationship("Incident", back_populates="nagios_comments")

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<NagiosComment {self.id} on {self.host_name}>"

    def to_dict(self) -> dict:
        """Convert Nagios comment to dictionary."""
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "author": self.author,
            "comment_data": self.comment_data,
            "host_name": self.host_name,
            "service_description": self.service_description,
        }


class PollMetadata(Base):
    """Track polling metadata and history."""

    __tablename__ = "poll_metadata"

    id = Column(Integer, primary_key=True)
    last_poll_time = Column(DateTime, nullable=False, index=True)
    status_dat_mtime = Column(DateTime, nullable=False)
    records_processed = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        """Return string representation."""
        return f"<PollMetadata {self.last_poll_time}>"

    def to_dict(self) -> dict:
        """Convert poll metadata to dictionary."""
        return {
            "id": self.id,
            "last_poll_time": self.last_poll_time.isoformat() if self.last_poll_time else None,
            "status_dat_mtime": self.status_dat_mtime.isoformat() if self.status_dat_mtime else None,
            "records_processed": self.records_processed,
        }

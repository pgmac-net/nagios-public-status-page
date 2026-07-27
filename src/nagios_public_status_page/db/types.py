"""Custom SQLAlchemy column types.

The application stores every timestamp as UTC. SQLite has no native timezone
support -- SQLAlchemy's SQLite dialect serialises a datetime to a string with no
offset and hands back a naive value on read, so ``DateTime(timezone=True)`` is a
no-op there. Worse, an aware value in a non-UTC zone is stored as its *local*
wall clock rather than being converted, which silently breaks ordering.

:class:`UTCDateTime` closes that gap: values are timezone-aware UTC everywhere in
Python, and naive UTC on disk. The storage format is byte-for-byte identical to
a plain ``DateTime`` column, so no data migration is required.
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):  # pylint: disable=too-many-ancestors,abstract-method
    """A ``DateTime`` column that is always timezone-aware UTC in Python.

    Naive values are rejected on write rather than coerced. A naive datetime
    carries no evidence of which zone it came from, so accepting one would mean
    guessing -- and guessing wrong stores local time that is indistinguishable
    from UTC once written. Failing loudly turns a missed call site into an
    immediate error instead of silently corrupt data.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        """Normalise an aware datetime to naive UTC for storage.

        Args:
            value: The datetime being written, or None
            dialect: The active SQLAlchemy dialect (unused)

        Returns:
            The equivalent naive UTC datetime, or None

        Raises:
            ValueError: If value is naive, since its intended zone is unknowable
        """
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                "Naive datetime rejected; timestamps must be timezone-aware UTC. "
                "Use datetime.now(UTC) or datetime.fromtimestamp(ts, UTC)."
            )
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        """Attach UTC to a naive value read back from the database.

        Args:
            value: The naive datetime read from storage, or None
            dialect: The active SQLAlchemy dialect (unused)

        Returns:
            The equivalent timezone-aware UTC datetime, or None
        """
        if value is None:
            return None
        return value.replace(tzinfo=UTC)

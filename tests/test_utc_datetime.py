"""Tests for the UTCDateTime column type and the UTC storage invariant."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import Integer, create_engine, select
from sqlalchemy.exc import StatementError
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from nagios_public_status_page.db.types import UTCDateTime


class Base(DeclarativeBase):
    """Declarative base for the throwaway table used in these tests."""


class Sample(Base):
    """Minimal table exercising the UTCDateTime column type."""

    __tablename__ = "sample"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ts: Mapped[datetime] = mapped_column(UTCDateTime)


@pytest.fixture
def session():
    """Provide a session against an in-memory SQLite database."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_roundtrip_returns_aware_utc(session):
    """A stored aware value reads back as aware UTC, not naive."""
    session.add(Sample(id=1, ts=datetime(2026, 7, 27, 12, 0, tzinfo=UTC)))
    session.commit()
    session.expunge_all()

    result = session.execute(select(Sample)).scalar_one()

    assert result.ts.tzinfo is not None
    assert result.ts == datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def test_naive_value_is_rejected(session):
    """Writing a naive datetime raises rather than silently storing local time."""
    # Deliberately naive: this is the value the type must reject.
    session.add(Sample(id=1, ts=datetime(2026, 7, 27, 12, 0)))  # noqa: DTZ001

    with pytest.raises(StatementError) as exc_info:
        session.commit()

    assert "timezone-aware UTC" in str(exc_info.value)


def test_non_utc_offset_is_converted_not_stored_as_wall_clock(session):
    """A +10:00 value is converted to UTC, not stored as its local wall clock.

    This is the corruption case a plain DateTime column allows: SQLAlchemy's
    SQLite dialect would store 22:00 for a value that is really 12:00 UTC,
    which silently breaks ordering against UTC rows.
    """
    aest = timezone(timedelta(hours=10))
    session.add(Sample(id=1, ts=datetime(2026, 7, 27, 22, 0, tzinfo=aest)))
    session.commit()

    stored = session.connection().exec_driver_sql("SELECT ts FROM sample").scalar_one()
    assert stored.startswith("2026-07-27 12:00:00")

    session.expunge_all()
    result = session.execute(select(Sample)).scalar_one()
    assert result.ts == datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def test_none_roundtrips(session):
    """Nullable timestamps are passed through untouched in both directions."""

    class Nullable(Base):
        __tablename__ = "nullable"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)
        ts: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    Base.metadata.create_all(session.get_bind())
    session.add(Nullable(id=1, ts=None))
    session.commit()
    session.expunge_all()

    assert session.execute(select(Nullable)).scalar_one().ts is None


def test_storage_format_matches_plain_datetime_column(session):
    """Storage is byte-identical to a plain DateTime column, so no migration.

    Existing rows were written by a plain DateTime column holding UTC values;
    this asserts UTCDateTime reads and writes that exact same representation.
    """
    session.connection().exec_driver_sql(
        "INSERT INTO sample (id, ts) VALUES (1, '2026-07-27 12:00:00.000000')"
    )
    session.commit()

    result = session.execute(select(Sample)).scalar_one()
    assert result.ts == datetime(2026, 7, 27, 12, 0, tzinfo=UTC)

    session.add(Sample(id=2, ts=datetime(2026, 7, 27, 13, 0, tzinfo=UTC)))
    session.commit()
    written = session.connection().exec_driver_sql(
        "SELECT ts FROM sample WHERE id = 2"
    ).scalar_one()
    assert written == "2026-07-27 13:00:00.000000"

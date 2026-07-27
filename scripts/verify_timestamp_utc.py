#!/usr/bin/env python3
"""Report whether stored timestamps look like UTC. Read-only.

The application stores every timestamp as UTC (see docs/UTC_TIMESTAMPS.md). Rows
written before that invariant was made explicit inherited whatever timezone the
container happened to run in, so this script checks the existing data rather
than assuming.

It compares the newest ``poll_metadata.last_poll_time`` against the current UTC
time. A healthy database polls every few minutes, so that gap should be small.
A gap close to a whole number of hours points at rows written in a non-UTC zone.

This script only issues SELECT statements. It never modifies the database.

Usage:
    python scripts/verify_timestamp_utc.py /path/to/status.db
"""

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

# A poll interval plus generous slack. Beyond this, the offset is suspicious.
EXPECTED_MAX_LAG_SECONDS = 3600


def _parse(value: str | None) -> datetime | None:
    """Parse a stored timestamp string as naive UTC.

    Args:
        value: Raw column value, or None

    Returns:
        The parsed datetime with UTC attached, or None
    """
    if not value:
        return None
    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def verify(db_path: str) -> int:
    """Report the apparent timezone of stored timestamps.

    Args:
        db_path: Path to the SQLite database

    Returns:
        Process exit code: 0 if timestamps look like UTC, 1 otherwise
    """
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        cursor = conn.cursor()
        now = datetime.now(UTC)
        print(f"Current UTC time:     {now.isoformat()}")

        cursor.execute("SELECT MAX(last_poll_time) FROM poll_metadata")
        last_poll = _parse(cursor.fetchone()[0])

        if last_poll is None:
            print("\nNo poll_metadata rows found; nothing to verify.")
            return 0

        lag = (now - last_poll).total_seconds()
        print(f"Newest last_poll_time: {last_poll.isoformat()} (read as UTC)")
        print(f"Lag behind now:        {lag:.0f}s ({lag / 3600:.2f}h)")

        cursor.execute("SELECT COUNT(*), MIN(started_at), MAX(started_at) FROM incidents")
        count, oldest, newest = cursor.fetchone()
        print(f"\nIncidents:             {count}")
        if count:
            print(f"  oldest started_at:   {oldest}")
            print(f"  newest started_at:   {newest}")

        if abs(lag) <= EXPECTED_MAX_LAG_SECONDS:
            print("\nRESULT: timestamps are consistent with UTC storage.")
            return 0

        print(
            f"\nRESULT: newest poll is {lag / 3600:.2f}h from now, which exceeds the "
            f"{EXPECTED_MAX_LAG_SECONDS / 3600:.0f}h threshold."
        )
        print(
            "This means either the poller has been stopped for that long, or the "
            "rows were written in a non-UTC timezone. Check whether the container "
            "is currently running before concluding the data needs migrating."
        )
        return 1
    finally:
        conn.close()


def main() -> None:
    """Run the verification."""
    if len(sys.argv) != 2:
        print("Usage: python scripts/verify_timestamp_utc.py <path_to_database>")
        print("Example: python scripts/verify_timestamp_utc.py data/status.db")
        sys.exit(1)

    db_path = Path(sys.argv[1])
    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    sys.exit(verify(str(db_path)))


if __name__ == "__main__":
    main()

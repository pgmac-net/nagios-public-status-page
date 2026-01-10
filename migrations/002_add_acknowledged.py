#!/usr/bin/env python3
"""Add acknowledged column to incidents table."""

import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str) -> None:
    """Add acknowledged column to incidents table.

    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists (safety check)
        cursor.execute("PRAGMA table_info(incidents)")
        columns = [row[1] for row in cursor.fetchall()]

        if "acknowledged" in columns:
            print("Column 'acknowledged' already exists. Skipping migration.")
            return

        # Add the new column
        print("Adding 'acknowledged' column to incidents table...")
        cursor.execute("""
            ALTER TABLE incidents
            ADD COLUMN acknowledged INTEGER NOT NULL DEFAULT 0
        """)

        conn.commit()
        print("Migration completed successfully!")
    except sqlite3.Error as e:
        print(f"Error during migration: {e}")
        conn.rollback()
        sys.exit(1)
    finally:
        conn.close()


def main() -> None:
    """Run the migration."""
    if len(sys.argv) != 2:
        print("Usage: python 002_add_acknowledged.py <path_to_database>")
        print("Example: python 002_add_acknowledged.py data/status.db")
        sys.exit(1)

    db_path = Path(sys.argv[1])

    if not db_path.exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    migrate(str(db_path))


if __name__ == "__main__":
    main()

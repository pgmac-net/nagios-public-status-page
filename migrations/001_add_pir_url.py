"""Migration: Add post_incident_review_url column to incidents table.

This migration adds support for linking incidents to post-incident review
documents stored in external repositories (e.g., GitHub).

Usage:
    python migrations/001_add_pir_url.py /path/to/status.db
"""

import sqlite3
import sys
from pathlib import Path


def migrate(db_path: str) -> None:
    """Add post_incident_review_url column to incidents table.

    Args:
        db_path: Path to SQLite database file
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(incidents)")
        columns = [row[1] for row in cursor.fetchall()]

        if "post_incident_review_url" in columns:
            print("Column 'post_incident_review_url' already exists. Skipping migration.")
            return

        # Add the new column
        print("Adding 'post_incident_review_url' column to incidents table...")
        cursor.execute("""
            ALTER TABLE incidents
            ADD COLUMN post_incident_review_url VARCHAR(512)
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
    """Main entry point."""
    if len(sys.argv) != 2:
        print("Usage: python migrations/001_add_pir_url.py /path/to/status.db")
        sys.exit(1)

    db_path = sys.argv[1]

    if not Path(db_path).exists():
        print(f"Error: Database file not found: {db_path}")
        sys.exit(1)

    migrate(db_path)


if __name__ == "__main__":
    main()

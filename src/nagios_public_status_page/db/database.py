"""Database initialization and session management."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from nagios_public_status_page.models import Base


class Database:
    """Database manager for SQLite."""

    def __init__(self, db_path: str):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.engine = None
        self.session_factory = None

    def initialize(self) -> None:
        """Initialize database engine and create tables if needed."""
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Create engine
        database_url = f"sqlite:///{self.db_path}"
        self.engine = create_engine(
            database_url,
            echo=False,
            connect_args={"check_same_thread": False},  # Needed for SQLite with FastAPI
        )

        # Create tables
        Base.metadata.create_all(self.engine)

        # Create session factory
        self.session_factory = sessionmaker(bind=self.engine, expire_on_commit=False)

    def get_session(self) -> Session:
        """Get a new database session.

        Returns:
            SQLAlchemy Session object

        Raises:
            RuntimeError: If database has not been initialized
        """
        if not self.session_factory:
            raise RuntimeError("Database not initialized. Call initialize() first.")

        return self.session_factory()

    def close(self) -> None:
        """Close database connection."""
        if self.engine:
            self.engine.dispose()


# Global database instance
_db_instance: Database | None = None


def get_database(db_path: str | None = None) -> Database:
    """Get or create global database instance.

    Args:
        db_path: Path to database file. Required on first call.

    Returns:
        Database instance

    Raises:
        RuntimeError: If db_path is None and database hasn't been initialized
    """
    global _db_instance

    if _db_instance is None:
        if db_path is None:
            raise RuntimeError("db_path required for first database initialization")
        _db_instance = Database(db_path)
        _db_instance.initialize()

    return _db_instance


def get_session() -> Session:
    """Get a database session from the global instance.

    Returns:
        SQLAlchemy Session

    Raises:
        RuntimeError: If database hasn't been initialized
    """
    if _db_instance is None:
        raise RuntimeError("Database not initialized. Call get_database() first.")

    return _db_instance.get_session()

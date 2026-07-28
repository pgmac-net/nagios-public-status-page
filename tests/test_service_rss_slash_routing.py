"""Tests that service RSS feeds handle slashes and special characters in descriptions.

Service descriptions like "CPU / Load" or "Disk Space, /var" were unreachable via
the RSS feed because a literal slash in the path segment would not match the route
pattern. Fixed by changing the route to use {service_description:path} converter,
which accepts slashes both raw and percent-encoded.
"""

from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
from starlette.testclient import TestClient

from nagios_public_status_page.main import app
from nagios_public_status_page.models import Incident


@pytest.fixture
def client_with_db(tmp_path):
    """Test client with temp database and incident fixture."""
    from nagios_public_status_page.api.routes import get_db as real_get_db
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from nagios_public_status_page.models import Base

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[real_get_db] = override_get_db
    client = TestClient(app)

    # Populate with recent incidents so filtering passes
    session = SessionLocal()
    session.add(
        Incident(
            incident_type="service",
            host_name="macro",
            service_description="CPU / Load",
            state=2,
            started_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    session.add(
        Incident(
            incident_type="service",
            host_name="macro",
            service_description="Disk Space, /var",
            state=2,
            started_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    session.commit()
    session.close()

    yield client
    app.dependency_overrides.clear()


def test_service_rss_with_slash_raw(client_with_db):
    """Raw (unencoded) slash in service description reaches the feed."""
    response = client_with_db.get("/feed/service/macro/CPU / Load/rss.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")
    assert "CPU / Load" in response.text


def test_service_rss_with_slash_encoded(client_with_db):
    """Percent-encoded slash reaches the feed."""
    encoded = quote("Disk Space, /var", safe="")
    response = client_with_db.get(f"/feed/service/macro/{encoded}/rss.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")


def test_service_rss_still_404_nonexistent(client_with_db):
    """No match still 404s when no incidents exist."""
    response = client_with_db.get("/feed/service/macro/Nonexistent/rss.xml")
    assert response.status_code == 404

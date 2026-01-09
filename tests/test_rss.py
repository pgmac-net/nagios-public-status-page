"""Tests for RSS feed generation."""

from datetime import datetime, timedelta
from xml.etree import ElementTree

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from status_page.config import RSSConfig
from status_page.models import Base, Incident
from status_page.rss.feed_generator import IncidentFeedGenerator


@pytest.fixture
def test_db():
    """Create a test database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def rss_config():
    """Create a test RSS configuration."""
    return RSSConfig(
        title="Test Status Page",
        description="Test status updates",
        link="https://status.test.com",
        max_items=50,
    )


@pytest.fixture
def feed_generator(rss_config):
    """Create a test feed generator."""
    return IncidentFeedGenerator(rss_config, base_url="https://status.test.com")


@pytest.fixture
def sample_incidents(test_db):
    """Create sample incidents for testing."""
    now = datetime.now()

    # Active host incident
    host_incident = Incident(
        incident_type="host",
        host_name="webserver01",
        service_description=None,
        state="DOWN",
        started_at=now - timedelta(hours=2),
        ended_at=None,
        last_check=now - timedelta(minutes=5),
        plugin_output="Host unreachable",
    )
    test_db.add(host_incident)

    # Resolved service incident
    service_incident = Incident(
        incident_type="service",
        host_name="webserver01",
        service_description="HTTP",
        state="CRITICAL",
        started_at=now - timedelta(hours=4),
        ended_at=now - timedelta(hours=1),
        last_check=now - timedelta(hours=1),
        plugin_output="Connection refused",
    )
    test_db.add(service_incident)

    # Active service incident for different host
    service_incident2 = Incident(
        incident_type="service",
        host_name="dbserver01",
        service_description="MySQL",
        state="WARNING",
        started_at=now - timedelta(minutes=30),
        ended_at=None,
        last_check=now - timedelta(minutes=5),
        plugin_output="Slow queries detected",
    )
    test_db.add(service_incident2)

    test_db.commit()
    return [host_incident, service_incident, service_incident2]


def test_create_base_feed(feed_generator, rss_config):
    """Test base feed creation."""
    feed = feed_generator._create_base_feed()

    assert feed.title() == rss_config.title
    assert feed.description() == rss_config.description
    assert feed.language() == "en"


def test_generate_global_feed(feed_generator, test_db, sample_incidents):
    """Test global RSS feed generation."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    # Parse XML to verify structure
    root = ElementTree.fromstring(feed_xml)

    # Check channel exists
    channel = root.find("channel")
    assert channel is not None

    # Check title
    title = channel.find("title")
    assert title is not None
    assert title.text == "Test Status Page"

    # Check items (should have 3 incidents)
    items = channel.findall("item")
    assert len(items) == 3


def test_generate_global_feed_respects_hours(feed_generator, test_db, sample_incidents):
    """Test that global feed respects the hours parameter."""
    # Only get incidents from last 3 hours (should exclude the 4-hour-old incident)
    feed_xml = feed_generator.generate_global_feed(test_db, hours=3)

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")
    items = channel.findall("item")

    # Should have 2 incidents (not the 4-hour-old one)
    assert len(items) == 2


def test_generate_host_feed(feed_generator, test_db, sample_incidents):
    """Test host-specific RSS feed generation."""
    feed_xml = feed_generator.generate_host_feed(test_db, "webserver01", hours=24)

    assert feed_xml is not None

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")

    # Check title includes host name
    title = channel.find("title")
    assert "webserver01" in title.text

    # Should have 2 incidents for webserver01
    items = channel.findall("item")
    assert len(items) == 2


def test_generate_host_feed_no_incidents(feed_generator, test_db, sample_incidents):
    """Test host feed returns None when no incidents exist."""
    feed_xml = feed_generator.generate_host_feed(test_db, "nonexistent", hours=24)

    assert feed_xml is None


def test_generate_service_feed(feed_generator, test_db, sample_incidents):
    """Test service-specific RSS feed generation."""
    feed_xml = feed_generator.generate_service_feed(
        test_db, "webserver01", "HTTP", hours=24
    )

    assert feed_xml is not None

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")

    # Check title includes service name
    title = channel.find("title")
    assert "webserver01/HTTP" in title.text

    # Should have 1 incident for this service
    items = channel.findall("item")
    assert len(items) == 1


def test_generate_service_feed_no_incidents(feed_generator, test_db, sample_incidents):
    """Test service feed returns None when no incidents exist."""
    feed_xml = feed_generator.generate_service_feed(
        test_db, "webserver01", "HTTPS", hours=24
    )

    assert feed_xml is None


def test_feed_entry_contains_required_fields(feed_generator, test_db, sample_incidents):
    """Test that feed entries contain all required fields."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")
    item = channel.find("item")

    # Check required RSS fields
    assert item.find("title") is not None
    assert item.find("guid") is not None
    assert item.find("link") is not None
    assert item.find("pubDate") is not None
    assert item.find("description") is not None


def test_feed_entry_active_incident(feed_generator, test_db, sample_incidents):
    """Test feed entry for active incident."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")
    items = channel.findall("item")

    # Find an active incident (should say ACTIVE in description)
    active_items = [
        item for item in items if "ACTIVE" in item.find("description").text
    ]
    assert len(active_items) >= 1


def test_feed_entry_resolved_incident(feed_generator, test_db, sample_incidents):
    """Test feed entry for resolved incident."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")
    items = channel.findall("item")

    # Find resolved incidents (should say RESOLVED in description)
    resolved_items = [
        item for item in items if "RESOLVED" in item.find("description").text
    ]
    assert len(resolved_items) >= 1


def test_feed_respects_max_items(test_db, rss_config):
    """Test that feed respects max_items configuration."""
    # Create many incidents
    now = datetime.now()
    for i in range(100):
        incident = Incident(
            incident_type="host",
            host_name=f"host{i:03d}",
            service_description=None,
            state="DOWN",
            started_at=now - timedelta(hours=i),
            ended_at=None,
            last_check=now,
            plugin_output=f"Test incident {i}",
        )
        test_db.add(incident)
    test_db.commit()

    # Set max_items to 10
    config = RSSConfig(
        title="Test",
        description="Test",
        link="https://test.com",
        max_items=10,
    )
    generator = IncidentFeedGenerator(config)

    feed_xml = generator.generate_global_feed(test_db, hours=200)

    root = ElementTree.fromstring(feed_xml)
    channel = root.find("channel")
    items = channel.findall("item")

    # Should only have 10 items
    assert len(items) == 10

"""Tests that RSS feed links point at URLs that actually resolve.

Before this fix, both the channel <link> and the self-referencing atom:link
advertised /feed.rss, which has never been a route -- the router is mounted at
/feed with a /rss.xml route, giving /feed/rss.xml. All three feed types (global,
host, service) shared the same hardcoded self-link too, so a host feed
advertised the global feed's URL. The existing RSS tests checked pubDate and
required fields but never that a link resolves, which is how this went
unnoticed (#65).

Link resolution is checked by fetching the advertised URL through the real app
via TestClient, rather than by re-implementing FastAPI's route matching --
FastAPI 0.140 flattens `include_router` lazily into internal `_IncludedRouter`
wrappers rather than plain `APIRoute` objects, so walking `app.routes` by hand
does not see routes registered this way.
"""

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from nagios_public_status_page.api.routes import get_db
from nagios_public_status_page.config import RSSConfig
from nagios_public_status_page.main import app
from nagios_public_status_page.models import Base, Incident
from nagios_public_status_page.rss.feed_generator import IncidentFeedGenerator

RSS_NS = {"atom": "http://www.w3.org/2005/Atom"}


@pytest.fixture
def db_engine():
    """Create a temporary file-based database engine.

    A plain "sqlite://" in-memory database gives each new connection its own
    separate database, so the tables created here would be invisible to the
    connection TestClient's get_db override opens later on the same engine.
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as temp_db:
        db_path = temp_db.name

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
    Path(db_path).unlink(missing_ok=True)


@pytest.fixture
def test_db(db_engine):
    """Create a database session bound to db_engine."""
    session_factory = sessionmaker(bind=db_engine)
    session = session_factory()
    yield session
    session.close()


@pytest.fixture
def client(db_engine):
    """Test client whose get_db dependency shares db_engine with test_db."""

    def override_get_db():
        session_factory = sessionmaker(bind=db_engine)
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


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
def incident(test_db):
    """Create and persist a single host incident."""
    incident = Incident(
        incident_type="host",
        host_name="macro",
        state=1,
        # Recent, not a fixed calendar date: generate_*_feed only includes
        # incidents within its hours window (default 24), and a hardcoded date
        # ages out of that window as soon as more than 24h pass (#71).
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(incident)
    test_db.commit()
    return incident


def _self_link(feed_xml: str) -> str:
    """Extract the href of atom:link rel="self" from feed XML."""
    root = ElementTree.fromstring(feed_xml)
    link = root.find("./channel/atom:link[@rel='self']", RSS_NS)
    assert link is not None, "feed has no atom:link rel=self"
    return link.attrib["href"]


def _channel_link(feed_xml: str) -> str:
    """Extract the channel's plain <link> element."""
    root = ElementTree.fromstring(feed_xml)
    link = root.find("./channel/link")
    assert link is not None
    return link.text


def _entry_link(feed_xml: str) -> str:
    """Extract the <link> of the first <item>."""
    root = ElementTree.fromstring(feed_xml)
    link = root.find("./channel/item/link")
    assert link is not None
    return link.text


def _path_of(url: str) -> str:
    """Strip the scheme and host from a self-link, leaving the request path."""
    from urllib.parse import urlparse

    return urlparse(url).path


def test_global_feed_self_link_resolves(feed_generator, test_db, client, incident):
    """The global feed's self-link must be a real, fetchable route."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    self_link = _self_link(feed_xml)

    assert self_link == "https://status.test.com/feed/rss.xml"
    response = client.get(_path_of(self_link))
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/rss+xml")


def test_host_feed_self_link_resolves_and_is_host_specific(
    feed_generator, test_db, client, incident
):
    """The host feed must advertise its own URL, not the global feed's."""
    feed_xml = feed_generator.generate_host_feed(test_db, "macro", hours=24)

    self_link = _self_link(feed_xml)

    assert self_link == "https://status.test.com/feed/host/macro/rss.xml"
    response = client.get(_path_of(self_link))
    assert response.status_code == 200


def test_service_feed_self_link_resolves_and_is_service_specific(
    feed_generator, test_db, client
):
    """The service feed must advertise its own URL, not the global feed's."""
    incident = Incident(
        incident_type="service",
        host_name="macro",
        service_description="HTTP",
        state=1,
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(incident)
    test_db.commit()

    feed_xml = feed_generator.generate_service_feed(test_db, "macro", "HTTP", hours=24)

    self_link = _self_link(feed_xml)

    assert self_link == "https://status.test.com/feed/service/macro/HTTP/rss.xml"
    response = client.get(_path_of(self_link))
    assert response.status_code == 200


def test_a_route_typo_would_be_caught_as_a_routing_miss(client):
    """Sanity check that the assertions above can actually fail.

    A URL that matches no route gets Starlette's generic 404, distinguishable
    from the handler's own "no incidents for this host" 404 by its detail.
    """
    response = client.get("/feed/this-path-does-not-exist")

    assert response.status_code == 404
    assert response.json()["detail"] == "Not Found"


def test_service_feed_self_link_encodes_special_characters(feed_generator, test_db):
    """A service description with a comma and spaces must be percent-encoded.

    Real Nagios service descriptions look like this. An unencoded self-link
    would embed raw spaces and a comma in the URL.
    """
    incident = Incident(
        incident_type="service",
        host_name="macro",
        service_description="Disk Space, /var",
        state=1,
        started_at=datetime.now(UTC) - timedelta(hours=1),
    )
    test_db.add(incident)
    test_db.commit()

    feed_xml = feed_generator.generate_service_feed(test_db, "macro", "Disk Space, /var", hours=24)

    self_link = _self_link(feed_xml)

    assert " " not in self_link
    assert self_link == (
        "https://status.test.com/feed/service/macro/Disk%20Space%2C%20%2Fvar/rss.xml"
    )


def test_channel_link_is_the_status_page_not_a_feed_url(feed_generator, test_db, incident):
    """<link> must be the site itself, per the RSS 2.0 spec -- not a feed URL.

    Before the fix this held the self href instead, because feedgen's RSS 2.0
    output takes the href of whichever link() call was made last, regardless of
    rel -- it does not distinguish alternate from self for that element.
    """
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    assert _channel_link(feed_xml) == "https://status.test.com"


def test_entry_link_resolves_to_the_status_page(feed_generator, test_db, incident):
    """Entries have no per-incident page to link to, so they link to the site."""
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)

    assert _entry_link(feed_xml) == "https://status.test.com"


def test_entry_guid_is_unchanged_by_this_fix(feed_generator, test_db, incident):
    """The entry id/guid must stay the /incidents/{id} form.

    It is rendered as <guid isPermaLink="false">, so it does not need to
    resolve -- only to be stable. Changing it would make every existing item
    look new to subscribers and re-fire notifications for incidents they have
    already seen.
    """
    feed_xml = feed_generator.generate_global_feed(test_db, hours=24)
    root = ElementTree.fromstring(feed_xml)
    guid = root.find("./channel/item/guid")

    assert guid is not None
    assert guid.text == f"https://status.test.com/incidents/{incident.id}"
    assert guid.attrib.get("isPermaLink") == "false"

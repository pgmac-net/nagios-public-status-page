"""Tests for the incident tracker."""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from status_page.collector.incident_tracker import IncidentTracker
from status_page.models import Base, Incident, NagiosComment


@pytest.fixture
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def tracker(db_session):
    """Create an incident tracker instance."""
    return IncidentTracker(db_session)


def test_process_host_creates_incident_for_down_host(tracker, db_session):
    """Test that a DOWN host creates a new incident."""
    host_data = {
        "host_name": "webserver01",
        "current_state": 1,  # DOWN
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Host is down",
    }

    incident = tracker.process_host(host_data)

    assert incident is not None
    assert incident.incident_type == "host"
    assert incident.host_name == "webserver01"
    assert incident.state == "DOWN"
    assert incident.ended_at is None
    assert incident.is_active


def test_process_host_updates_existing_incident(tracker, db_session):
    """Test that processing a problem host updates existing incident."""
    # Create initial incident
    host_data = {
        "host_name": "webserver01",
        "current_state": 1,  # DOWN
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Host is down",
    }
    incident1 = tracker.process_host(host_data)
    incident1_id = incident1.id

    # Process again with updated output
    host_data["plugin_output"] = "Host still down"
    incident2 = tracker.process_host(host_data)

    assert incident2.id == incident1_id
    assert incident2.plugin_output == "Host still down"
    assert incident2.is_active


def test_process_host_closes_incident_when_recovered(tracker, db_session):
    """Test that a recovered host closes the incident."""
    # Create incident
    host_data = {
        "host_name": "webserver01",
        "current_state": 1,  # DOWN
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Host is down",
    }
    incident = tracker.process_host(host_data)
    assert incident.is_active

    # Host recovers
    host_data["current_state"] = 0  # UP
    host_data["plugin_output"] = "Host is up"
    recovered = tracker.process_host(host_data)

    assert recovered.id == incident.id
    assert recovered.ended_at is not None
    assert not recovered.is_active


def test_process_service_creates_incident_for_critical_service(tracker, db_session):
    """Test that a CRITICAL service creates a new incident."""
    service_data = {
        "host_name": "webserver01",
        "service_description": "HTTP",
        "current_state": 2,  # CRITICAL
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Connection refused",
    }

    incident = tracker.process_service(service_data)

    assert incident is not None
    assert incident.incident_type == "service"
    assert incident.host_name == "webserver01"
    assert incident.service_description == "HTTP"
    assert incident.state == "CRITICAL"
    assert incident.is_active


def test_process_service_creates_incident_for_warning(tracker, db_session):
    """Test that a WARNING service creates an incident."""
    service_data = {
        "host_name": "webserver01",
        "service_description": "HTTPS",
        "current_state": 1,  # WARNING
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Certificate expiring soon",
    }

    incident = tracker.process_service(service_data)

    assert incident is not None
    assert incident.state == "WARNING"
    assert incident.is_active


def test_process_service_doesnt_create_incident_for_ok(tracker, db_session):
    """Test that an OK service doesn't create an incident."""
    service_data = {
        "host_name": "webserver01",
        "service_description": "HTTP",
        "current_state": 0,  # OK
        "last_check": datetime.now().timestamp(),
        "plugin_output": "HTTP OK",
    }

    incident = tracker.process_service(service_data)
    assert incident is None


def test_get_active_incidents(tracker, db_session):
    """Test retrieving active incidents."""
    # Create multiple incidents
    for i in range(3):
        host_data = {
            "host_name": f"server{i}",
            "current_state": 1,
            "last_check": datetime.now().timestamp(),
            "plugin_output": "Down",
        }
        tracker.process_host(host_data)

    # Resolve one
    host_data = {
        "host_name": "server1",
        "current_state": 0,
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Up",
    }
    tracker.process_host(host_data)

    active = tracker.get_active_incidents()
    assert len(active) == 2
    assert all(inc.ended_at is None for inc in active)


def test_get_recent_incidents(tracker, db_session):
    """Test retrieving recent incidents."""
    # Create old incident
    old_incident = Incident(
        incident_type="host",
        host_name="oldserver",
        state="DOWN",
        started_at=datetime.now() - timedelta(hours=48),
        ended_at=datetime.now() - timedelta(hours=47),
        last_check=datetime.now() - timedelta(hours=47),
        plugin_output="Old problem",
    )
    db_session.add(old_incident)

    # Create recent incident
    host_data = {
        "host_name": "newserver",
        "current_state": 1,
        "last_check": datetime.now().timestamp(),
        "plugin_output": "Recent problem",
    }
    tracker.process_host(host_data)
    db_session.commit()

    recent = tracker.get_recent_incidents(hours=24)
    assert len(recent) == 1
    assert recent[0].host_name == "newserver"


def test_process_nagios_comment(tracker, db_session):
    """Test processing Nagios comments."""
    comment_data = {
        "host_name": "webserver01",
        "service_description": None,
        "entry_time": datetime.now().timestamp(),
        "author": "admin",
        "comment_data": "Working on issue",
    }

    comment = tracker.process_nagios_comment(comment_data)

    assert comment is not None
    assert comment.host_name == "webserver01"
    assert comment.author == "admin"
    assert comment.comment_data == "Working on issue"


def test_link_comment_to_incident(tracker, db_session):
    """Test linking comments to incidents."""
    # Create incident
    now = datetime.now()
    incident = Incident(
        incident_type="host",
        host_name="webserver01",
        state="DOWN",
        started_at=now - timedelta(minutes=10),
        last_check=now,
        plugin_output="Host down",
    )
    db_session.add(incident)
    db_session.commit()

    # Create comment during incident
    comment = NagiosComment(
        entry_time=now - timedelta(minutes=5),
        author="admin",
        comment_data="Investigating",
        host_name="webserver01",
    )
    db_session.add(comment)
    db_session.commit()

    # Link them
    tracker.link_comment_to_incident(comment, incident)

    assert comment.incident_id == incident.id


def test_cleanup_old_incidents(tracker, db_session):
    """Test cleanup of old closed incidents."""
    # Create old closed incident
    old_incident = Incident(
        incident_type="host",
        host_name="oldserver",
        state="DOWN",
        started_at=datetime.now() - timedelta(days=40),
        ended_at=datetime.now() - timedelta(days=39),
        last_check=datetime.now() - timedelta(days=39),
        plugin_output="Old problem",
    )
    db_session.add(old_incident)

    # Create recent closed incident
    recent_incident = Incident(
        incident_type="host",
        host_name="recentserver",
        state="DOWN",
        started_at=datetime.now() - timedelta(days=2),
        ended_at=datetime.now() - timedelta(days=1),
        last_check=datetime.now() - timedelta(days=1),
        plugin_output="Recent problem",
    )
    db_session.add(recent_incident)
    db_session.commit()

    # Cleanup incidents older than 30 days
    deleted = tracker.cleanup_old_incidents(days=30)

    assert deleted == 1
    remaining = db_session.query(Incident).all()
    assert len(remaining) == 1
    assert remaining[0].host_name == "recentserver"


def test_state_name_conversion(tracker):
    """Test state code to name conversion."""
    assert tracker._get_state_name("host", 0) == "UP"
    assert tracker._get_state_name("host", 1) == "DOWN"
    assert tracker._get_state_name("service", 0) == "OK"
    assert tracker._get_state_name("service", 1) == "WARNING"
    assert tracker._get_state_name("service", 2) == "CRITICAL"


def test_is_problem_state(tracker):
    """Test problem state detection."""
    assert not tracker._is_problem_state("host", 0)  # UP
    assert tracker._is_problem_state("host", 1)  # DOWN
    assert not tracker._is_problem_state("service", 0)  # OK
    assert tracker._is_problem_state("service", 1)  # WARNING
    assert tracker._is_problem_state("service", 2)  # CRITICAL

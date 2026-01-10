"""Tests for the status.dat parser."""

from pathlib import Path

import pytest

from nagios_public_status_page.parser.status_dat import StatusDatParser


@pytest.fixture
def sample_status_dat():
    """Return path to sample status.dat fixture."""
    return Path(__file__).parent / "fixtures" / "sample_status.dat"


@pytest.fixture
def parser(sample_status_dat):
    """Return initialized parser with sample data."""
    parser = StatusDatParser(sample_status_dat)
    parser.parse()
    return parser


def test_parser_initialization(sample_status_dat):
    """Test parser can be initialized with a file path."""
    parser = StatusDatParser(sample_status_dat)
    assert parser.status_dat_path == sample_status_dat
    assert parser.data == {}


def test_parser_parse(parser):
    """Test parser can parse status.dat file."""
    assert "hoststatus" in parser.data
    assert "servicestatus" in parser.data
    assert "programstatus" in parser.data


def test_parser_gets_hosts(parser):
    """Test parser can extract all hosts."""
    hosts = parser.get_hosts()
    assert len(hosts) == 3
    host_names = [h["host_name"] for h in hosts]
    assert "webserver01" in host_names
    assert "dbserver01" in host_names
    assert "internal-server" in host_names


def test_parser_filters_hosts_by_hostgroup(parser):
    """Test parser can filter hosts by hostgroup."""
    public_hosts = parser.get_hosts(hostgroups=["public-status"])
    assert len(public_hosts) == 2

    host_names = [h["host_name"] for h in public_hosts]
    assert "webserver01" in host_names
    assert "dbserver01" in host_names
    assert "internal-server" not in host_names


def test_parser_filters_hosts_multiple_hostgroups(parser):
    """Test parser can filter hosts by multiple hostgroups."""
    hosts = parser.get_hosts(hostgroups=["public-status", "internal-only"])
    assert len(hosts) == 3  # All hosts match at least one group


def test_parser_gets_services(parser):
    """Test parser can extract all services."""
    services = parser.get_services()
    assert len(services) == 4

    service_names = [s["service_description"] for s in services]
    assert "HTTP" in service_names
    assert "HTTPS" in service_names
    assert "MySQL" in service_names
    assert "Disk Space" in service_names


def test_parser_filters_services_by_servicegroup(parser):
    """Test parser can filter services by servicegroup."""
    public_services = parser.get_services(servicegroups=["public-status-services"])
    assert len(public_services) == 3

    service_descs = [s["service_description"] for s in public_services]
    assert "HTTP" in service_descs
    assert "HTTPS" in service_descs
    assert "MySQL" in service_descs
    assert "Disk Space" not in service_descs


def test_parser_extracts_host_state(parser):
    """Test parser correctly extracts host states."""
    hosts = parser.get_hosts()

    webserver = next(h for h in hosts if h["host_name"] == "webserver01")
    assert webserver["current_state"] == 0  # UP

    dbserver = next(h for h in hosts if h["host_name"] == "dbserver01")
    assert dbserver["current_state"] == 1  # DOWN


def test_parser_extracts_service_state(parser):
    """Test parser correctly extracts service states."""
    services = parser.get_services()

    http = next(s for s in services if s["service_description"] == "HTTP")
    assert http["current_state"] == 0  # OK

    https = next(s for s in services if s["service_description"] == "HTTPS")
    assert https["current_state"] == 1  # WARNING

    mysql = next(s for s in services if s["service_description"] == "MySQL")
    assert mysql["current_state"] == 2  # CRITICAL


def test_parser_extracts_plugin_output(parser):
    """Test parser correctly extracts plugin output."""
    hosts = parser.get_hosts()
    webserver = next(h for h in hosts if h["host_name"] == "webserver01")
    assert "PING OK" in webserver["plugin_output"]

    services = parser.get_services()
    https = next(s for s in services if s["service_description"] == "HTTPS")
    assert "Certificate expires" in https["plugin_output"]


def test_parser_gets_comments(parser):
    """Test parser can extract comments."""
    comments = parser.get_comments()
    assert len(comments) == 2

    # Check host comment
    host_comment = next(c for c in comments if "host_name" in c and c["host_name"] == "dbserver01")
    assert host_comment["author"] == "admin"
    assert "network issues" in host_comment["comment_data"]

    # Check service comment
    service_comment = next(
        c for c in comments if "service_description" in c and c["service_description"] == "HTTPS"
    )
    assert service_comment["author"] == "sysadmin"
    assert "SSL certificate" in service_comment["comment_data"]


def test_parser_gets_program_status(parser):
    """Test parser can extract program status."""
    prog_status = parser.get_program_status()
    assert prog_status is not None
    assert prog_status["daemon_mode"] == 1
    assert prog_status["enable_notifications"] == 1


def test_parser_type_conversion(parser):
    """Test parser correctly converts types."""
    hosts = parser.get_hosts()
    webserver = hosts[0]

    # Integers
    assert isinstance(webserver["current_state"], int)
    assert isinstance(webserver["max_attempts"], int)

    # Floats
    assert isinstance(webserver["check_interval"], float)
    assert isinstance(webserver["check_execution_time"], float)

    # Strings
    assert isinstance(webserver["host_name"], str)
    assert isinstance(webserver["plugin_output"], str)


def test_parser_file_mtime_tracking(parser):
    """Test parser tracks file modification time."""
    assert parser.file_mtime is not None


def test_parser_data_age(parser):
    """Test parser can calculate data age."""
    age = parser.get_data_age_seconds()
    assert age is not None
    assert age >= 0


def test_parser_staleness_detection(parser):
    """Test parser can detect stale data."""
    # Data from fixture file should be considered stale with a very low threshold
    assert parser.is_data_stale(1)

    # But not stale with a very high threshold
    assert not parser.is_data_stale(999999999)


def test_parser_missing_file():
    """Test parser handles missing file gracefully."""
    parser = StatusDatParser("/nonexistent/path/status.dat")

    with pytest.raises(FileNotFoundError):
        parser.parse()

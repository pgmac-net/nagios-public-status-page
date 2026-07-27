"""Tests that documented environment variables actually override configuration.

docker-compose.yml and .env.example advertise a set of variables. Every one of
them must be read by load_config(), or a deployment silently runs on the
config.yaml defaults while appearing to be configured.
"""

import re
import tempfile
from pathlib import Path

import pytest
import yaml

from nagios_public_status_page.config import load_config

REPO_ROOT = Path(__file__).parent.parent

BASE_CONFIG = {
    "nagios": {"status_dat_path": "/nagios/var/status.dat"},
    "polling": {"interval_seconds": 300, "staleness_threshold_seconds": 600},
    "api": {"host": "0.0.0.0", "port": 8000, "cors_origins": ["*"]},
    "rss": {
        "title": "System Status",
        "description": "Public status updates",
        "link": "https://status.example.com",
        "max_items": 50,
    },
}


@pytest.fixture
def config_file():
    """Write a baseline config.yaml and return its path."""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as handle:
        yaml.safe_dump(BASE_CONFIG, handle)
        path = handle.name

    yield path

    Path(path).unlink(missing_ok=True)


def _declared_vars(text: str) -> set[str]:
    """Extract environment variable names assigned in a config file."""
    return set(re.findall(r"^#?\s*-?\s*([A-Z][A-Z0-9_]+)=", text, re.MULTILINE))


def _read_vars() -> set[str]:
    """Return every variable name load_config() consults."""
    source = (REPO_ROOT / "src" / "nagios_public_status_page" / "config.py").read_text()
    return set(re.findall(r'os\.getenv\("([A-Z0-9_]+)"', source))


def test_every_compose_variable_is_read_by_the_app():
    """A variable set in docker-compose.yml must reach the configuration.

    POLLING_INTERVAL_SECONDS and POLLING_STALENESS_THRESHOLD_SECONDS were set
    here for a long time while the loader read POLL_INTERVAL_SECONDS and
    STALENESS_THRESHOLD_SECONDS, so both were silently ignored.
    """
    declared = _declared_vars((REPO_ROOT / "docker-compose.yml").read_text())

    # TZ is consumed by the operating system, not by load_config().
    unread = declared - _read_vars() - {"TZ"}

    assert not unread, f"docker-compose.yml sets variables the app never reads: {sorted(unread)}"


def test_every_documented_env_example_variable_is_read_by_the_app():
    """.env.example must not advertise variables that do nothing."""
    declared = _declared_vars((REPO_ROOT / ".env.example").read_text())

    unread = declared - _read_vars() - {"TZ"}

    assert not unread, f".env.example documents variables the app never reads: {sorted(unread)}"


def test_rss_link_override(config_file, monkeypatch):
    """RSS_LINK overrides the configured feed link."""
    monkeypatch.setenv("RSS_LINK", "https://statuspage.example.net")

    assert load_config(config_file).rss.link == "https://statuspage.example.net"


def test_rss_description_override(config_file, monkeypatch):
    """RSS_DESCRIPTION overrides the configured feed description."""
    monkeypatch.setenv("RSS_DESCRIPTION", "Live service status")

    assert load_config(config_file).rss.description == "Live service status"


def test_rss_max_items_override(config_file, monkeypatch):
    """RSS_MAX_ITEMS is coerced to an integer."""
    monkeypatch.setenv("RSS_MAX_ITEMS", "20")

    assert load_config(config_file).rss.max_items == 20


def test_cors_origins_override_splits_on_commas(config_file, monkeypatch):
    """API_CORS_ORIGINS accepts a comma-separated list."""
    monkeypatch.setenv("API_CORS_ORIGINS", "https://a.example.com, https://b.example.com")

    assert load_config(config_file).api.cors_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_polling_overrides_use_the_documented_names(config_file, monkeypatch):
    """The poll interval responds to POLL_INTERVAL_SECONDS."""
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "60")
    monkeypatch.setenv("STALENESS_THRESHOLD_SECONDS", "120")

    config = load_config(config_file)

    assert config.polling.interval_seconds == 60
    assert config.polling.staleness_threshold_seconds == 120


def test_unset_variables_leave_config_values_intact(config_file, monkeypatch):
    """An empty value falls through to config.yaml rather than blanking it.

    docker-compose.yml passes ${GRAPH_SIGNING_SECRET:-} and friends, so unset
    secrets arrive as empty strings. Those must not override the file.
    """
    monkeypatch.setenv("RSS_TITLE", "")
    monkeypatch.setenv("RSS_LINK", "")

    config = load_config(config_file)

    assert config.rss.title == "System Status"
    assert config.rss.link == "https://status.example.com"

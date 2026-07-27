"""Configuration management for the status page application."""

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ServiceSpec(BaseModel):
    """Specification for a service to monitor."""

    host_name: str = Field(..., description="Host name")
    service_description: str = Field(..., description="Service description")


class NagiosConfig(BaseModel):
    """Nagios-related configuration."""

    status_dat_path: str = Field(
        default="/usr/local/nagios/var/status.dat",
        description="Path to Nagios status.dat file",
    )
    hostgroups: list[str] = Field(
        default_factory=list, description="Hostgroups to monitor"
    )
    servicegroups: list[str] = Field(
        default_factory=list, description="Servicegroups to monitor"
    )
    hosts: list[str] = Field(
        default_factory=list, description="Explicit list of host names to monitor"
    )
    services: list[ServiceSpec] = Field(
        default_factory=list, description="Explicit list of services to monitor"
    )


class PollingConfig(BaseModel):
    """Polling configuration."""

    interval_seconds: int = Field(default=300, description="How often to poll status.dat")
    staleness_threshold_seconds: int = Field(
        default=600, description="Data age threshold for staleness warning"
    )


class DatabaseConfig(BaseModel):
    """Database configuration."""

    path: str = Field(default="./data/status.db", description="Path to SQLite database")


class APIConfig(BaseModel):
    """API server configuration."""

    host: str = Field(default="0.0.0.0", description="API host to bind to")
    port: int = Field(default=8000, description="API port to listen on")
    cors_origins: list[str] = Field(
        default_factory=lambda: ["*"], description="CORS allowed origins"
    )
    basic_auth_username: str | None = Field(
        default=None, description="Username for Basic Auth (write operations only)"
    )
    basic_auth_password: str | None = Field(
        default=None, description="Password for Basic Auth (write operations only)"
    )


class GraphConfig(BaseModel):
    """Signed nagiosgraph proxy configuration."""

    nagiosgraph_url: str | None = Field(
        default=None,
        description="Base URL of the internal nagiosgraph CGI (e.g. http://nagios.int/cgi-bin)",
    )
    signing_secret: str | None = Field(
        default=None, description="Shared HMAC secret used to sign/verify graph URLs"
    )
    default_ttl_seconds: int = Field(
        default=604800, description="Default signature lifetime for generated graph URLs (7 days)"
    )
    basic_auth_username: str | None = Field(
        default=None, description="Username for nagiosgraph CGI basic auth, if required"
    )
    basic_auth_password: str | None = Field(
        default=None, description="Password for nagiosgraph CGI basic auth, if required"
    )


class RSSConfig(BaseModel):
    """RSS feed configuration."""

    title: str = Field(default="System Status", description="RSS feed title")
    description: str = Field(default="Public status updates", description="RSS feed description")
    link: str = Field(default="https://status.example.com", description="RSS feed link")
    max_items: int = Field(default=50, description="Maximum items in RSS feed")


class IncidentsConfig(BaseModel):
    """Incidents configuration."""

    retention_days: int = Field(default=30, description="Days to keep closed incidents")


class CommentsConfig(BaseModel):
    """Comments configuration."""

    pull_nagios_comments: bool = Field(
        default=True, description="Whether to pull comments from Nagios"
    )


class Config(BaseModel):
    """Main application configuration."""

    nagios: NagiosConfig = Field(default_factory=NagiosConfig)
    polling: PollingConfig = Field(default_factory=PollingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    graph: GraphConfig = Field(default_factory=GraphConfig)
    rss: RSSConfig = Field(default_factory=RSSConfig)
    incidents: IncidentsConfig = Field(default_factory=IncidentsConfig)
    comments: CommentsConfig = Field(default_factory=CommentsConfig)


def load_config(config_path: str | Path = "config.yaml") -> Config:
    """Load configuration from YAML file, with environment variable overrides.

    Environment variables take precedence over config file values.
    Use uppercase with underscores, e.g., NAGIOS_STATUS_DAT_PATH.

    The YAML file is optional. When absent, configuration comes entirely from
    environment variables and the defaults declared on the models above, which
    lets a container run from .env alone. The file remains the right place for
    structured settings -- notably ``nagios.services``, whose environment
    equivalent cannot represent a service description containing a comma.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Loaded configuration object

    Raises:
        ValidationError: If any supplied setting fails validation
    """
    config_path = Path(config_path)
    config_data: dict[str, Any] = {}

    if config_path.exists():
        with open(config_path, encoding="utf-8") as file:
            # An empty file parses to None, which is a valid way to say
            # "configure everything from the environment".
            config_data = yaml.safe_load(file) or {}

    # Override with environment variables if present
    if status_dat_path := os.getenv("NAGIOS_STATUS_DAT_PATH"):
        config_data.setdefault("nagios", {})["status_dat_path"] = status_dat_path

    if hostgroups := os.getenv("NAGIOS_HOSTGROUPS"):
        config_data.setdefault("nagios", {})["hostgroups"] = [
            hg.strip() for hg in hostgroups.split(",")
        ]

    if servicegroups := os.getenv("NAGIOS_SERVICEGROUPS"):
        config_data.setdefault("nagios", {})["servicegroups"] = [
            sg.strip() for sg in servicegroups.split(",")
        ]

    if hosts := os.getenv("NAGIOS_HOSTS"):
        config_data.setdefault("nagios", {})["hosts"] = [
            h.strip() for h in hosts.split(",")
        ]

    if services := os.getenv("NAGIOS_SERVICES"):
        # Format: "host1:service1,host2:service2"
        service_list = []
        for svc in services.split(","):
            if ":" in svc:
                host, service = svc.split(":", 1)
                service_list.append({
                    "host_name": host.strip(),
                    "service_description": service.strip()
                })
        config_data.setdefault("nagios", {})["services"] = service_list

    if poll_interval := os.getenv("POLL_INTERVAL_SECONDS"):
        config_data.setdefault("polling", {})["interval_seconds"] = int(poll_interval)

    if staleness_threshold := os.getenv("STALENESS_THRESHOLD_SECONDS"):
        config_data.setdefault("polling", {})["staleness_threshold_seconds"] = int(
            staleness_threshold
        )

    if db_path := os.getenv("DATABASE_PATH"):
        config_data.setdefault("database", {})["path"] = db_path

    if api_host := os.getenv("API_HOST"):
        config_data.setdefault("api", {})["host"] = api_host

    if api_port := os.getenv("API_PORT"):
        config_data.setdefault("api", {})["port"] = int(api_port)

    if auth_username := os.getenv("API_BASIC_AUTH_USERNAME"):
        config_data.setdefault("api", {})["basic_auth_username"] = auth_username

    if auth_password := os.getenv("API_BASIC_AUTH_PASSWORD"):
        config_data.setdefault("api", {})["basic_auth_password"] = auth_password

    if nagiosgraph_url := os.getenv("GRAPH_NAGIOSGRAPH_URL"):
        config_data.setdefault("graph", {})["nagiosgraph_url"] = nagiosgraph_url

    if signing_secret := os.getenv("GRAPH_SIGNING_SECRET"):
        config_data.setdefault("graph", {})["signing_secret"] = signing_secret

    if graph_ttl := os.getenv("GRAPH_DEFAULT_TTL_SECONDS"):
        config_data.setdefault("graph", {})["default_ttl_seconds"] = int(graph_ttl)

    if graph_auth_username := os.getenv("GRAPH_BASIC_AUTH_USERNAME"):
        config_data.setdefault("graph", {})["basic_auth_username"] = graph_auth_username

    if graph_auth_password := os.getenv("GRAPH_BASIC_AUTH_PASSWORD"):
        config_data.setdefault("graph", {})["basic_auth_password"] = graph_auth_password

    if rss_title := os.getenv("RSS_TITLE"):
        config_data.setdefault("rss", {})["title"] = rss_title

    if rss_link := os.getenv("RSS_LINK"):
        config_data.setdefault("rss", {})["link"] = rss_link

    if rss_description := os.getenv("RSS_DESCRIPTION"):
        config_data.setdefault("rss", {})["description"] = rss_description

    if rss_max_items := os.getenv("RSS_MAX_ITEMS"):
        config_data.setdefault("rss", {})["max_items"] = int(rss_max_items)

    if cors_origins := os.getenv("API_CORS_ORIGINS"):
        config_data.setdefault("api", {})["cors_origins"] = [
            origin.strip() for origin in cors_origins.split(",")
        ]

    # Add the remaining env overrides for fields that previously had none
    if retention_days := os.getenv("INCIDENTS_RETENTION_DAYS"):
        config_data.setdefault("incidents", {})["retention_days"] = int(retention_days)

    if pull_comments := os.getenv("COMMENTS_PULL_NAGIOS_COMMENTS"):
        config_data.setdefault("comments", {})["pull_nagios_comments"] = (
            pull_comments.strip().lower() in {"1", "true", "yes", "on"}
        )

    # Validate and create config object
    return Config(**config_data)

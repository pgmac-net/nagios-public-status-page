"""Parser for Nagios status.dat files."""

import os
from datetime import datetime
from pathlib import Path
from typing import Any


class StatusDatParser:
    """Parse Nagios status.dat files and extract host/service status information."""

    def __init__(self, status_dat_path: str):
        """Initialize the parser with the path to status.dat.

        Args:
            status_dat_path: Path to the Nagios status.dat file
        """
        self.status_dat_path = Path(status_dat_path)
        self.data: dict[str, list[dict[str, Any]]] = {}
        self.file_mtime: datetime | None = None

    def parse(self) -> dict[str, list[dict[str, Any]]]:
        """Parse the status.dat file and return structured data.

        Returns:
            Dictionary containing parsed data with keys like 'hoststatus', 'servicestatus', etc.

        Raises:
            FileNotFoundError: If status.dat file doesn't exist
            PermissionError: If status.dat file cannot be read
        """
        if not self.status_dat_path.exists():
            raise FileNotFoundError(f"Status file not found: {self.status_dat_path}")

        # Get file modification time
        stat_info = os.stat(self.status_dat_path)
        self.file_mtime = datetime.fromtimestamp(stat_info.st_mtime)

        self.data = {}
        current_section = None
        current_block: dict[str, Any] = {}

        with open(self.status_dat_path, encoding="utf-8") as file:
            for line in file:
                line = line.strip()

                # Skip empty lines and comments
                if not line or line.startswith("#"):
                    continue

                # Start of a new section (e.g., "hoststatus {")
                if line.endswith("{"):
                    section_name = line[:-1].strip()
                    current_section = section_name
                    current_block = {}

                # End of a section
                elif line == "}":
                    if current_section and current_block:
                        if current_section not in self.data:
                            self.data[current_section] = []
                        self.data[current_section].append(current_block)
                    current_section = None
                    current_block = {}

                # Key-value pair within a section
                elif "=" in line and current_section:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()

                    # Convert numeric strings to appropriate types
                    if value.isdigit():
                        current_block[key] = int(value)
                    elif value.replace(".", "", 1).isdigit():
                        current_block[key] = float(value)
                    else:
                        current_block[key] = value

        return self.data

    def get_hosts(
        self,
        hostgroups: list[str] | None = None,
        explicit_hosts: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get host status information, filtered by hostgroups and/or explicit host list.

        Args:
            hostgroups: List of hostgroup names to filter by. If None, skip
                        hostgroup filtering.
            explicit_hosts: List of explicit host names to include. If None, skip
                            explicit filtering.

        Returns:
            List of host status dictionaries
        """
        hosts = self.data.get("hoststatus", [])

        # If no filtering specified, return all hosts
        if not hostgroups and not explicit_hosts:
            return hosts

        filtered_hosts = []
        for host in hosts:
            host_name = host.get("host_name", "")

            # Check if host matches explicit list
            if explicit_hosts and host_name in explicit_hosts:
                filtered_hosts.append(host)
                continue

            # Check if host matches hostgroup
            if hostgroups:
                host_groups = host.get("host_groups", "")
                if host_groups:
                    groups = [g.strip() for g in host_groups.split(",")]
                    if any(hg in groups for hg in hostgroups):
                        filtered_hosts.append(host)

        return filtered_hosts

    def get_services(
        self,
        servicegroups: list[str] | None = None,
        explicit_services: list[tuple[str, str]] | None = None,
    ) -> list[dict[str, Any]]:
        """Get service status information, filtered by servicegroups and/or explicit service list.

        Args:
            servicegroups: List of servicegroup names to filter by. If None, skip
                           servicegroup filtering.
            explicit_services: List of (host_name, service_description) tuples to include.
                             If None, skip explicit filtering.

        Returns:
            List of service status dictionaries
        """
        services = self.data.get("servicestatus", [])

        # If no filtering specified, return all services
        if not servicegroups and not explicit_services:
            return services

        filtered_services = []
        for service in services:
            host_name = service.get("host_name", "")
            service_description = service.get("service_description", "")

            # Check if service matches explicit list
            if explicit_services:
                if (host_name, service_description) in explicit_services:
                    filtered_services.append(service)
                    continue

            # Check if service matches servicegroup
            if servicegroups:
                service_groups = service.get("service_groups", "")
                if service_groups:
                    groups = [g.strip() for g in service_groups.split(",")]
                    if any(sg in groups for sg in servicegroups):
                        filtered_services.append(service)

        return filtered_services

    def get_comments(self) -> list[dict[str, Any]]:
        """Get all comments from status.dat.

        Returns:
            List of comment dictionaries
        """
        host_comments = self.data.get("hostcomment", [])
        service_comments = self.data.get("servicecomment", [])
        return host_comments + service_comments

    def get_program_status(self) -> dict[str, Any] | None:
        """Get Nagios program status information.

        Returns:
            Program status dictionary or None if not found
        """
        program_status = self.data.get("programstatus", [])
        return program_status[0] if program_status else None

    def is_data_stale(self, threshold_seconds: int) -> bool:
        """Check if the status.dat file data is stale.

        Args:
            threshold_seconds: Maximum age in seconds before data is considered stale

        Returns:
            True if data is older than threshold, False otherwise
        """
        if not self.file_mtime:
            return True

        age = (datetime.now() - self.file_mtime).total_seconds()
        return age > threshold_seconds

    def get_data_age_seconds(self) -> float | None:
        """Get the age of the status.dat data in seconds.

        Returns:
            Age in seconds or None if file has not been parsed
        """
        if not self.file_mtime:
            return None

        return (datetime.now() - self.file_mtime).total_seconds()

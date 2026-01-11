[![Build and push nagios-public-status-page](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/build.yml/badge.svg)](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/build.yml)
[![App test, build and publish to PyPI](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/python-app.yml/badge.svg)](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/python-app.yml)
[![CodeQL](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/codeql.yml/badge.svg)](https://github.com/pgmac-net/nagios-public-status-page/actions/workflows/codeql.yml)\
[![codecov](https://codecov.io/gh/pgmac-net/nagios-public-status-page/branch/main/graph/badge.svg)](https://codecov.io/gh/pgmac-net/nagios-public-status-page)
![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/pgmac-net/nagios-public-status-page/badge)\
![PyPI Python versions](https://img.shields.io/pypi/pyversions/nagios-public-status-page.svg)
![PyPI version](https://img.shields.io/pypi/v/nagios-public-status-page.svg)\
![PyPI downloads](https://img.shields.io/pypi/dm/nagios-public-status-page)
![Docker Pulls](https://img.shields.io/docker/pulls/pgmac/nagios-public-status-page.svg)\
![license](https://img.shields.io/github/license/pgmac-net/nagios-public-status-page.svg)
![uv-managed](https://img.shields.io/badge/uv-managed-blueviolet)

# Public Status Page for Nagios

A standalone public status page application that displays selected hosts and services from your Nagios monitoring system.

**📦 PyPI:** [https://pypi.org/project/nagios-public-status-page/](https://pypi.org/project/nagios-public-status-page/)\
**🐳 Docker Hub:** [https://hub.docker.com/r/pgmac/nagios-public-status-page](https://hub.docker.com/r/pgmac/nagios-public-status-page)\
**📦 GitHub Container Registry:** [https://github.com/pgmac-net/nagios-public-status-page/pkgs/container/nagios-public-status-page](https://github.com/pgmac-net/nagios-public-status-page/pkgs/container/nagios-public-status-page)

## Features

- Reads from Nagios `status.dat` file (no additional plugins required)
- Filters hosts and services by hostgroups and servicegroups
- Configurable polling interval
- Tracks incidents with start/end times
- Manual status comments and updates
- Optional Nagios comment integration
- **Post-Incident Review (PIR) document linking** - Link resolved incidents to their PIR docs
- RSS feeds (global, per-host, per-service)
- Data staleness detection and warnings
- RESTful API for extensibility
- Completely separate from Nagios
- Simple deployment with SQLite

## Architecture

The application consists of several components:

1. **Status.dat Parser**: Parses Nagios status.dat and filters by hostgroups/servicegroups
2. **Data Collector**: Background poller that tracks incidents and state changes
3. **REST API**: FastAPI-based API for querying status and managing comments
4. **RSS Feed Generator**: Generates RSS feeds for incidents
5. **Database**: SQLite database for incidents, comments, and metadata

## Requirements

- Python 3.11+
- Access to Nagios `status.dat` file
- UV package manager (recommended) or pip

## Installation

### From PyPI (Recommended)

The easiest way to install is directly from PyPI:

```bash
# Install the package
pip install nagios-public-status-page

# Or using pipx for isolated installation
pipx install nagios-public-status-page

# Run the status page CLI
status-page --help
```

The PyPI package includes:

- Python package with all dependencies
- CLI command: `status-page`
- All static web assets
- Example configuration files

### From Source with UV

```bash
# Clone the repository
git clone https://github.com/pgmac/nagios-public-status-page.git
cd nagios-public-status-page

# UV will automatically create a virtual environment and install dependencies
uv sync
```

### From Source with pip

```bash
# Clone the repository
git clone https://github.com/pgmac/nagios-public-status-page.git
cd nagios-public-status-page

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode
pip install -e .
```

## Quick Start

After installing from PyPI:

```bash
# 1. Install the package
pip install nagios-public-status-page

# 2. Create a basic config file
cat > config.yaml << EOF
nagios:
  status_dat_path: "/usr/local/nagios/var/status.dat"
  hostgroups:
    - "public-status"
  servicegroups:
    - "public-status-services"

polling:
  interval_seconds: 300

database:
  path: "./data/status.db"

api:
  host: "0.0.0.0"
  port: 8000
EOF

# 3. Run the status page
status-page
# Or using Python module directly
python -m nagios_public_status_page.main

# 4. Access the dashboard
# Open http://localhost:8000 in your browser
```

## Configuration

### 1. Choose Your Filtering Method

The public status page supports two methods for filtering which hosts and services to display:

#### Method A: Hostgroups and Servicegroups (Recommended)

In your Nagios configuration, create hostgroups and servicegroups for public display:

```
# In your Nagios host definition
define host {
    host_name           webserver01
    address             192.168.1.10
    hostgroups          linux-servers,public-status  # Add to public-status
    ...
}

# In your Nagios service definition
define service {
    service_description HTTP
    host_name           webserver01
    servicegroups       web-services,public-status-services  # Add to public group
    ...
}
```

**Note**: This method requires that Nagios writes `host_groups` and `service_groups` fields to status.dat. Some Nagios configurations may not include these fields.

#### Method B: Explicit Host and Service Lists

If your Nagios doesn't write group fields to status.dat, you can explicitly list which hosts and services to monitor in `config.yaml`:

```yaml
nagios:
  status_dat_path: "/usr/local/nagios/var/status.dat"
  hosts:
    - "webserver01"
    - "dbserver01"
  services:
    - host_name: "macro"
      service_description: "plexweb"
    - host_name: "webserver01"
      service_description: "HTTP"
```

You can also use environment variables:

```bash
NAGIOS_HOSTS="webserver01,dbserver01"
NAGIOS_SERVICES="macro:plexweb,webserver01:HTTP"
```

**Tip**: You can combine both methods - the status page will include hosts/services that match _either_ the groups _or_ the explicit lists.

### 2. Configure the Application

Copy the example config and customize:

```bash
cp .env.example .env
# Edit config.yaml with your settings
```

Key configuration options in `config.yaml`:

```yaml
nagios:
  status_dat_path: "/usr/local/nagios/var/status.dat"
  hostgroups:
    - "public-status"
  servicegroups:
    - "public-status-services"

polling:
  interval_seconds: 300 # Poll every 5 minutes
  staleness_threshold_seconds: 600 # Warn if data > 10 minutes old

database:
  path: "./data/status.db"

api:
  host: "0.0.0.0"
  port: 8000
```

Environment variables override config file values. See `.env.example` for available variables.

## Deployment

Multiple deployment options are available:

### Quick Start with Docker

Pre-built images are available from Docker Hub and GitHub Container Registry:

```bash
# Pull from Docker Hub (recommended)
docker pull pgmac/nagios-public-status-page:latest

# Or pull from GitHub Container Registry
docker pull ghcr.io/pgmac/nagios-public-status-page:latest

# Run the container
docker run -d \
  -p 8000:8000 \
  -v /usr/local/nagios/var/status.dat:/app/status.dat:ro \
  -v ./config.yaml:/app/config.yaml:ro \
  -v ./data:/app/data \
  --name status-page \
  pgmac/nagios-public-status-page:latest

# Access the dashboard
open http://localhost:8000
```

**Available Image Tags:**

- `latest` - Latest stable release (semver tagged)
- `v1.0.0` - Specific version (replace with desired version)
- `v1.0` - Latest patch version in the 1.0 series
- `v1` - Latest minor version in the 1.x series
- `sha-<hash>` - Specific commit hash (for testing)

**Note:** Only semver-tagged releases (e.g., `v1.0.0`) are pushed to the registries to keep them clean. SHA-tagged images are built but not pushed.

### Quick Start with Docker Compose

```bash
# Edit docker-compose.yml to configure your Nagios status.dat path
docker-compose up -d

# View logs
docker-compose logs -f

# Access the dashboard
open http://localhost:8000
```

### Creating a Release

To publish a new version to Docker registries, PyPI, and GitHub Releases:

1. Create and push a semver tag (the version in `pyproject.toml` will be automatically updated):

   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```

2. GitHub Actions will automatically:
   - Run tests, linting, and type checks
   - Update version in `pyproject.toml` to match the tag
   - Build and publish Python package to PyPI
   - Create a GitHub Release with distribution files
   - Build and push Docker images to Docker Hub and GHCR with multiple tags

**Note:** The version in `pyproject.toml` is automatically updated from the git tag during the release process, so you don't need to manually update it before tagging.

### Other Deployment Options

- **Docker**: Containerized deployment with multi-stage builds
- **Systemd**: Linux service deployment
- **Manual**: Direct Python deployment

See **[DEPLOYMENT.md](DEPLOYMENT.md)** for complete deployment documentation including:

- Docker and Docker Compose setup
- Systemd service configuration
- Production best practices
- Security hardening
- Troubleshooting guide

## Usage

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=nagios_public_status_page
```

### Code Quality

```bash
# Run ruff linter
uv run ruff check src/ tests/

# Run pylint
uv run pylint src/nagios_public_status_page/

# Auto-fix issues
uv run ruff check --fix src/ tests/
```

## Project Status

### Phase 1: Core Parser & Data Model ✅ COMPLETED

- [x] Python project setup with UV
- [x] status.dat parser with hostgroup/servicegroup filtering
- [x] SQLAlchemy models and SQLite database
- [x] Configuration loader with environment variable support
- [x] Comprehensive test suite (17 tests passing)
- [x] Code quality checks (ruff + pylint: 9.63/10)

### Phase 2: Data Collector ✅ COMPLETED

- [x] Incident tracker service for host/service problems
- [x] Automatic incident creation, update, and closure
- [x] APScheduler background poller
- [x] Incident detection and tracking logic
- [x] Nagios comment extraction during incidents
- [x] Automatic comment linking to incidents
- [x] Staleness detection and warnings
- [x] Old incident cleanup
- [x] Comprehensive test suite (13 additional tests = 30 total)
- [x] Code quality checks (ruff + pylint: 9.74/10)

### Phase 3: REST API ✅ COMPLETED

- [x] FastAPI application with auto-generated docs
- [x] Pydantic schemas for type-safe API responses
- [x] Background poller integration (starts/stops with app)
- [x] Health check endpoint with staleness detection
- [x] Status summary endpoint (hosts/services counts)
- [x] Hosts and services listing endpoints
- [x] Incidents endpoint (filter by active/recent)
- [x] Individual incident detail endpoint with comments
- [x] POST endpoint to add comments to incidents
- [x] CORS middleware configuration
- [x] Comprehensive error handling
- [x] Code quality checks (ruff + pylint: 9.34/10)

### Phase 4: RSS Feeds ✅ COMPLETED

- [x] feedgen integration
- [x] IncidentFeedGenerator class with RSS generation
- [x] Global RSS feed for all incidents
- [x] Per-host RSS feeds
- [x] Per-service RSS feeds
- [x] Feed endpoints (GET /feed/rss, /feed/host/{name}/rss, /feed/service/{name}/{service}/rss)
- [x] Configurable max_items and feed metadata
- [x] Proper RSS XML formatting with pub dates and descriptions
- [x] Comprehensive test suite (11 additional tests = 41 total)
- [x] Code quality checks (ruff + pylint: 9.12/10)

### Phase 5: Frontend ✅ COMPLETED

- [x] Modern HTML5 dashboard with responsive design
- [x] CSS styling with gradient headers and card-based layout
- [x] JavaScript for API interaction (vanilla JS, no frameworks)
- [x] Real-time status summary display (hosts/services/incidents)
- [x] Incident list with active/recent/all filtering
- [x] Host and service status displays
- [x] Incident detail modal with comments
- [x] Comment submission form with validation
- [x] Staleness warning banner
- [x] Auto-refresh every 60 seconds
- [x] FastAPI static file serving configuration
- [x] Secure DOM manipulation (XSS protection)
- [x] RSS feed subscription links
- [x] All 41 tests passing
- [x] Code quality checks (ruff + pylint: 9.01/10)

### Phase 6: Deployment ✅ COMPLETED

- [x] Multi-stage Dockerfile for efficient containerization
- [x] docker-compose.yml for easy deployment
- [x] Comprehensive deployment documentation (DEPLOYMENT.md)
- [x] systemd service file for Linux deployments
- [x] .dockerignore for optimized builds
- [x] Docker build tested successfully (290MB image)
- [x] Health checks and security hardening

### Phase 7: Post-Incident Review Integration ✅ COMPLETED

- [x] Database schema: Added `post_incident_review_url` field to incidents table
- [x] Database migration script (001_add_pir_url.py)
- [x] API schemas updated to include PIR URL
- [x] PATCH endpoint to set/update PIR URLs (`/api/incidents/{id}/pir`)
- [x] Frontend displays PIR links in incident detail modal
- [x] Comprehensive test suite (10 additional tests = 51 total)
- [x] Documentation updated

## API Endpoints

```
GET   /api/status                                   - Overall system status
GET   /api/hosts                                    - Filtered host statuses
GET   /api/services                                 - Filtered service statuses
GET   /api/incidents                                - Active and recent incidents
GET   /api/incidents/{id}                           - Specific incident details
POST  /api/incidents/{id}/comments                  - Add manual status update
PATCH /api/incidents/{id}/pir                       - Link PIR document to incident
GET   /api/health                                   - Data freshness check
GET   /feed/rss                                     - RSS feed (all incidents)
GET   /feed/host/{host_name}/rss                    - Per-host RSS feed
GET   /feed/service/{host_name}/{service}/rss       - Per-service RSS feed
```

## Database Schema

The SQLite database includes:

- **incidents**: Host and service incidents with start/end times (includes `post_incident_review_url`)
- **comments**: Manual status updates
- **nagios_comments**: Comments pulled from Nagios
- **poll_metadata**: Polling history and metadata

## Post-Incident Review (PIR) Integration

Link resolved incidents to their post-incident review documents for better incident tracking and learning.

### Setting a PIR URL for an Incident

Use the PATCH endpoint to associate a PIR document with an incident:

```bash
curl -X PATCH http://localhost:8000/api/incidents/123/pir \
  -H "Content-Type: application/json" \
  -d '{"post_incident_review_url": "https://your-pir-docs.com/incidents/2025-01-10-incident/"}'
```

### Viewing PIR Links

PIR links appear:

- In the incident detail modal on the dashboard (with a document icon)
- In API responses for incidents (`GET /api/incidents/{id}` and `GET /api/incidents`)
- PIR URLs are optional and can be null for incidents without documentation

### Database Migration

If upgrading from an earlier version, run the migration to add the PIR URL column:

```bash
python migrations/001_add_pir_url.py data/status.db
```

## Development

### Project Structure

```
public-status-page/
   src/
      nagios_public_status_page/
          parser/          # status.dat parser
          collector/       # Background polling
          api/             # FastAPI routes
          rss/             # RSS feed generator
          db/              # Database setup
          models.py        # SQLAlchemy models
          config.py        # Configuration
   tests/                   # Test suite
   static/                  # Frontend files
   config.yaml              # Configuration
   pyproject.toml           # Dependencies
```

### Contributing

1. Ensure tests pass: `uv run pytest`
2. Run linters: `uv run ruff check src/ tests/`
3. Run pylint: `uv run pylint src/nagios_public_status_page/`

## Security & Code Quality

This project follows OpenSSF security best practices with automated scanning, dependency updates, and comprehensive code quality checks.

- **Report vulnerabilities**: See [SECURITY.md](SECURITY.md)
- **Security setup guide**: See [SECURITY_QUICKSTART.md](docs/SECURITY_QUICKSTART.md)
- **Repository security**: See [REPOSITORY_SECURITY.md](docs/REPOSITORY_SECURITY.md)
- **Code scanning & coverage**: See [CODE_SCANNING_SETUP.md](docs/CODE_SCANNING_SETUP.md)

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/pgmac-net/nagios-public-status-page/badge)](https://scorecard.dev/viewer/?uri=github.com/pgmac-net/nagios-public-status-page)

## License

MIT License - see [LICENSE](LICENSE) file for details

## Author

@pgmac

"""Main FastAPI application for the public status page."""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from nagios_public_status_page.api.routes import router, rss_router
from nagios_public_status_page.collector.poller import StatusPoller
from nagios_public_status_page.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Global poller instance
poller: StatusPoller | None = None

# Load configuration
try:
    config = load_config()
except FileNotFoundError:
    logger.error("Configuration file not found. Please create config.yaml")
    raise
except Exception as exc:
    logger.error("Failed to load configuration: %s", exc)
    raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start the background poller on application startup."""
    global poller
    logger.info("Starting application...")

    try:
        # Start the background poller
        poller = StatusPoller(config)
        poller.start()
        logger.info("Background poller started successfully")
    except Exception as exc:
        logger.error("Failed to start background poller: %s", exc)
        raise

    yield  # Do application stuff

    """Stop the background poller on application shutdown."""
    logger.info("Shutting down application...")

    if poller:
        try:
            poller.stop()
            logger.info("Background poller stopped successfully")
        except Exception as exc:
            logger.error("Error stopping background poller: %s", exc)


# Create FastAPI app
app = FastAPI(
    title="Nagios Public Status Page API",
    description="""
## Nagios Public Status Page API

A comprehensive REST API for monitoring Nagios infrastructure with incident tracking and RSS feeds.

### Features

* **Real-time Status Monitoring**: Get current status of hosts and services
* **Incident Management**: Track incidents with comments and post-incident reviews
* **RSS Feeds**: Subscribe to incident updates via RSS
* **Health Checks**: Monitor API and data freshness
* **Authentication**: Basic HTTP authentication for write operations

### Authentication

Write operations (POST, PATCH) require HTTP Basic Authentication when configured.
Set credentials in your `config.yaml` file.

### Getting Started

1. Check the API health: `GET /api/health`
2. View overall status: `GET /api/status`
3. List incidents: `GET /api/incidents`
4. Subscribe to RSS: `GET /feed/rss.xml`
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {
            "name": "api",
            "description": "Core API endpoints for monitoring and incident management",
        },
        {
            "name": "rss",
            "description": "RSS feed endpoints for incident notifications",
        },
    ],
    contact={
        "name": "GitHub Repository",
        "url": "https://github.com/pgmac/nagios-public-status-page",
    },
    license_info={
        "name": "MIT",
        "url": "https://github.com/pgmac/nagios-public-status-page/blob/main/LICENSE",
    },
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,  # ty: ignore[invalid-argument-type]
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)
app.include_router(rss_router)

# Mount static files
static_dir = Path(__file__).parent.parent.parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_model=None)
async def root() -> FileResponse | JSONResponse:
    """Serve the main dashboard page.

    Returns:
        HTML file response or JSON if static files not found
    """
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return JSONResponse(content={
        "message": "Nagios Public Status Page API",
        "version": "1.0.0",
        "docs": "/api/docs",
        "health": "/api/health",
    })


@app.get("/api")
async def api_info() -> JSONResponse:
    """API endpoint information.

    Returns:
        JSON response with available endpoints
    """
    return JSONResponse(
        content={
            "endpoints": {
                "GET /api/health": "Health check",
                "GET /api/status": "Overall status summary",
                "GET /api/hosts": "List all monitored hosts",
                "GET /api/services": "List all monitored services",
                "GET /api/incidents": "List incidents (query params: active_only, hours)",
                "GET /api/incidents/{id}": "Get incident details with comments",
                "POST /api/incidents/{id}/comments": "Add a comment to an incident",
                "GET /feed/rss": "Global RSS feed for all incidents",
                "GET /feed/host/{host_name}/rss": "RSS feed for specific host",
                "GET /feed/service/{host_name}/{service_description}/rss": "RSS feed for specific service",
            }
        }
    )


def main() -> None:
    """Main entry point for the status page application."""
    import uvicorn

    uvicorn.run(
        "nagios_public_status_page.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=False,
    )


if __name__ == "__main__":
    main()

"""Main FastAPI application for the public status page."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from status_page.api.routes import router
from status_page.collector.poller import StatusPoller
from status_page.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Load configuration
try:
    config = load_config()
except FileNotFoundError:
    logger.error("Configuration file not found. Please create config.yaml")
    raise
except Exception as exc:
    logger.error("Failed to load configuration: %s", exc)
    raise

# Create FastAPI app
app = FastAPI(
    title="Nagios Public Status Page",
    description="Public status page for Nagios monitoring",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)

# Global poller instance
poller: StatusPoller | None = None


@app.on_event("startup")
async def startup_event() -> None:
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


@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Stop the background poller on application shutdown."""
    global poller
    logger.info("Shutting down application...")

    if poller:
        try:
            poller.stop()
            logger.info("Background poller stopped successfully")
        except Exception as exc:
            logger.error("Error stopping background poller: %s", exc)


@app.get("/")
async def root() -> JSONResponse:
    """Root endpoint with API information.

    Returns:
        JSON response with API info
    """
    return JSONResponse(
        content={
            "message": "Nagios Public Status Page API",
            "version": "1.0.0",
            "docs": "/api/docs",
            "health": "/api/health",
        }
    )


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
            }
        }
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "status_page.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True,
    )

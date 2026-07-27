# Use single-stage build to avoid venv symlink issues
FROM python:3.14-slim

# OCI metadata labels
LABEL org.opencontainers.image.title="Nagios Public Status Page"
LABEL org.opencontainers.image.description="A standalone public status page application that displays selected hosts and services from your Nagios monitoring system"
LABEL org.opencontainers.image.authors="Paul Macdonnell <pgmac@pgmac.net>"
LABEL org.opencontainers.image.vendor="pgmac"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.url="https://github.com/pgmac/nagios-public-status-page"
LABEL org.opencontainers.image.source="https://github.com/pgmac/nagios-public-status-page"
LABEL org.opencontainers.image.documentation="https://github.com/pgmac/nagios-public-status-page#readme"

# Install uv and runtime dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 statuspage

# Set working directory and ensure ownership
WORKDIR /app
RUN chown -R statuspage:statuspage /app

# Copy dependency files
COPY --chown=statuspage:statuspage pyproject.toml ./
COPY --chown=statuspage:statuspage README.md ./
COPY --chown=statuspage:statuspage src/ ./src/

# Switch to non-root user for installation
USER statuspage

# Create data directory with correct permissions
RUN mkdir -p /app/data

# Install dependencies using uv sync (creates venv with correct Python paths)
RUN uv sync --no-dev

# Copy application files
COPY --chown=statuspage:statuspage static/ ./static/
# Ship the example as the in-image default. A deployment overrides it by
# bind-mounting its own config.yaml, or configures everything from the
# environment. config.yaml itself is gitignored, so it must not be COPYed --
# a clean clone does not have one and the build would fail.
COPY --chown=statuspage:statuspage config.yaml.example ./config.yaml

# Set environment variables
# TZ is pinned so the container's wall clock matches the UTC storage invariant.
# The application no longer depends on this (all timestamps are explicitly UTC),
# but pinning it keeps logs and any shell in the container consistent.
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TZ=UTC

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["uvicorn", "nagios_public_status_page.main:app", "--host", "0.0.0.0", "--port", "8000"]

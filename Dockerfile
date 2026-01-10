# Use single-stage build to avoid venv symlink issues
FROM python:3.11-slim

# Install uv and runtime dependencies
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 statuspage && \
    mkdir -p /app/data && \
    chown -R statuspage:statuspage /app

# Set working directory
WORKDIR /app

# Copy dependency files
COPY --chown=statuspage:statuspage pyproject.toml ./
COPY --chown=statuspage:statuspage README.md ./
COPY --chown=statuspage:statuspage src/ ./src/

# Switch to non-root user for installation
USER statuspage

# Install dependencies using uv sync (creates venv with correct Python paths)
RUN uv sync --no-dev

# Copy application files
COPY --chown=statuspage:statuspage static/ ./static/
COPY --chown=statuspage:statuspage config.yaml ./

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Expose API port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Run the application
CMD ["uvicorn", "status_page.main:app", "--host", "0.0.0.0", "--port", "8000"]

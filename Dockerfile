FROM ghcr.io/astral-sh/uv:python3.12-trixie-slim

# Create a non-root user
RUN groupadd -r agent && useradd -r -g agent -d /app agent

# Set working directory
WORKDIR /app
COPY pyproject.toml uv.lock ./
# Install dependencies using uv sync
RUN uv sync --locked

# Copy application code and dependency files
COPY app/ ./app/
COPY utils/ ./utils/

# Ensure files are owned by the non-root user
RUN chown -R agent:agent /app

# Switch to non-root user
USER agent

# Default environment variables (can be overridden)
ENV HOST=0.0.0.0
ENV PORT=8000
ENV WORKERS=2
ENV UV_NO_DEV=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1


# Metadata only, does not bind the port
EXPOSE $PORT

# Healthcheck using localhost
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD uv run python -c \
    "import os, urllib.request; p=os.getenv('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{p}/health')" \
    || exit 1

# Start the application
# Using shell form to allow $PORT expansion from environment
CMD uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2


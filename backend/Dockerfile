FROM python:3.12-slim-bookworm

# Install Noto fonts for CJK and Vietnamese/Latin PDF text insertion (Phase 3+)
# Install now so Phase 3 doesn't need a Dockerfile change (per CLAUDE.md)
RUN apt-get update && \
    apt-get install -y --no-install-recommends fonts-noto-cjk fonts-noto fontconfig && \
    fc-cache -f && \
    rm -rf /var/lib/apt/lists/*

# Install uv for fast Python dependency management
RUN pip install uv --no-cache-dir

WORKDIR /backend

# Copy dependency manifest first (layer cache: only reinstalls when pyproject.toml changes)
COPY pyproject.toml .

# Install all dependencies (including test extras) into the system Python
RUN uv pip install --system -e ".[test]"

# Copy alembic config — needed by `alembic current/upgrade` invoked via docker exec
COPY alembic.ini .

# Copy source code (bind-mounted in development; baked in production builds)
COPY src/ src/

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONPATH=/backend/src

EXPOSE 8000

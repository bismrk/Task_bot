# ==============================================================================
# Stage 1: Frontend Build Stage
# ==============================================================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend dependency manifests for Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Clean installation of frontend dependencies
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build production static assets (outputs to /app/frontend/dist)
RUN npm run build

# ==============================================================================
# Stage 2: Python Runtime Stage
# ==============================================================================
FROM python:3.11-slim AS python-runtime

# Ensure Python outputs are sent straight to terminal without buffering
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/app/.venv/bin:$PATH"

# Install uv package manager from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency specifications
COPY pyproject.toml uv.lock ./

# Install production dependencies using frozen lockfile
RUN uv sync --frozen --no-dev

# Copy backend application source code and runner
COPY src/ ./src/
COPY main.py ./

# Copy compiled frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create directory for persistent SQLite database
RUN mkdir -p /app/data

# Expose HTTP port
EXPOSE 8000

# Execute unified runner entrypoint
CMD ["uv", "run", "python", "main.py"]

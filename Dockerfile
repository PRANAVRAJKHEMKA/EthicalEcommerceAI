# ==============================================================================
# FairCart AI — Production Multi-Stage Container Definition
# Sized for zero-cost deployment on Render / Google Cloud Run / Hugging Face Spaces
# ==============================================================================

# ------------------------------------------------------------------------------
# Stage 1: Compile the React 19 Frontend SPA
# ------------------------------------------------------------------------------
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Leverage layer caching for dependencies
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source and build static artifacts into /app/frontend/dist
COPY frontend/ ./
RUN npm run build

# ------------------------------------------------------------------------------
# Stage 2: Minimal Python 3.12 Production Runtime
# ------------------------------------------------------------------------------
FROM python:3.12-slim AS runtime
WORKDIR /app

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    ENVIRONMENT=production

# Install curl for container health check probes
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install pinned Python dependencies
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r ./backend/requirements.txt

# Copy backend code, models, and scripts
COPY backend ./backend

# Copy compiled frontend assets from Stage 1 into the expected location
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose HTTP port (Render, Cloud Run, and HF Spaces bind dynamically via $PORT)
EXPOSE 8000

# Container healthcheck probe against the operational health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT:-8000}/api/v1/health || exit 1

# Launch FastAPI via Uvicorn with dynamic port binding.
# Backend startup hook (startup_event in backend.app.main) automatically
# seeds faircart.db with all 32 curated products on first boot.
CMD ["sh", "-c", "uvicorn backend.app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]

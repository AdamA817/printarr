# ====== Frontend Build Stage ======
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --silent

COPY frontend/ ./
RUN npm run build

# ====== Backend Build Stage ======
FROM python:3.11-slim AS backend-builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies as wheels
COPY backend/requirements.txt ./
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels -r requirements.txt

# ====== Final Image ======
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies and supervisor
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Copy Python wheels and install
COPY --from=backend-builder /wheels /wheels
RUN pip install --no-cache /wheels/* && rm -rf /wheels

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build to be served by FastAPI
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist/

# Copy Docker config files
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/supervisord.conf /etc/supervisor/conf.d/printarr.conf
RUN chmod +x /entrypoint.sh

# Create directories for volume mounts
RUN mkdir -p /config /data /staging /library /cache

# Environment defaults
ENV PRINTARR_HOST=0.0.0.0
ENV PRINTARR_PORT=3333
ENV PRINTARR_CONFIG_PATH=/config
ENV PRINTARR_DATA_PATH=/data
ENV PRINTARR_LIBRARY_PATH=/library
ENV PRINTARR_CACHE_PATH=/cache
ENV PRINTARR_DATABASE_URL=sqlite+aiosqlite:////config/printarr.db

EXPOSE 3333

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3333/api/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]

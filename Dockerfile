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
    # Archive extraction tools for v0.5
    unrar-free \
    p7zip-full \
    # OpenGL dependencies for stl-thumb headless rendering (v0.7)
    libgl1 \
    libglx-mesa0 \
    libegl1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install stl-thumb for STL preview rendering (v0.7)
# Download pre-built .deb from GitHub releases based on architecture
# Note: stl-thumb requires libosmesa6 for off-screen rendering
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends \
    libosmesa6-dev \
    && rm -rf /var/lib/apt/lists/* && \
    case ${TARGETARCH} in \
        "amd64") STL_THUMB_ARCH="amd64" ;; \
        "arm64") STL_THUMB_ARCH="arm64" ;; \
        *) echo "Unsupported architecture: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    curl -fsSL "https://github.com/unlimitedbacon/stl-thumb/releases/download/v0.5.0/stl-thumb_0.5.0_${STL_THUMB_ARCH}.deb" -o /tmp/stl-thumb.deb && \
    dpkg -i /tmp/stl-thumb.deb && \
    rm /tmp/stl-thumb.deb && \
    stl-thumb --version

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

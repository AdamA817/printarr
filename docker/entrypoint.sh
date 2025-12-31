#!/bin/bash
set -e

echo "==================================="
echo "  Printarr v0.7.0"
echo "==================================="

# Ensure volume directories exist
mkdir -p /config /data /staging /library /cache

# Create preview directory structure (v0.7 - DEC-027)
mkdir -p /cache/previews/telegram
mkdir -p /cache/previews/archive
mkdir -p /cache/previews/thangs
mkdir -p /cache/previews/embedded
mkdir -p /cache/previews/rendered

# Run database migrations
echo "Running database migrations..."
cd /app/backend
alembic upgrade head

# Start supervisor to manage processes
echo "Starting Printarr services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/printarr.conf

#!/bin/bash
set -e

echo "==================================="
echo "  Printarr v0.1.0"
echo "==================================="

# Ensure volume directories exist
mkdir -p /config /data /staging /library /cache

# Run database migrations
echo "Running database migrations..."
cd /app/backend
alembic upgrade head

# Start supervisor to manage processes
echo "Starting Printarr services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/printarr.conf

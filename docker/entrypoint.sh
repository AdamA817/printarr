#!/bin/bash
set -e

echo "==================================="
echo "  Printarr v0.8.0"
echo "==================================="

# Ensure volume directories exist
mkdir -p /config /data /staging /library /cache

# Create preview directory structure (v0.7 - DEC-027)
mkdir -p /cache/previews/telegram
mkdir -p /cache/previews/archive
mkdir -p /cache/previews/thangs
mkdir -p /cache/previews/embedded
mkdir -p /cache/previews/rendered

# PostgreSQL data directory (DEC-039)
PGDATA=/config/postgres

# Initialize PostgreSQL if this is a fresh install
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "Initializing PostgreSQL database cluster..."
    mkdir -p "$PGDATA"
    chown -R postgres:postgres "$PGDATA"

    # Initialize the database cluster
    su postgres -c "/usr/lib/postgresql/16/bin/initdb -D $PGDATA --encoding=UTF8 --locale=C"

    # Configure PostgreSQL for local connections only
    echo "host all all 127.0.0.1/32 trust" >> "$PGDATA/pg_hba.conf"
    echo "local all all trust" >> "$PGDATA/pg_hba.conf"

    # Start PostgreSQL temporarily to create the database and user
    echo "Starting PostgreSQL to create database..."
    su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA -l /tmp/postgres_init.log start"

    # Wait for PostgreSQL to be ready
    echo "Waiting for PostgreSQL to be ready..."
    for i in {1..30}; do
        if su postgres -c "/usr/lib/postgresql/16/bin/pg_isready -q"; then
            break
        fi
        sleep 1
    done

    # Create the printarr user and database
    echo "Creating printarr database and user..."
    su postgres -c "psql -c \"CREATE USER printarr WITH PASSWORD 'printarr';\""
    su postgres -c "psql -c \"CREATE DATABASE printarr OWNER printarr;\""
    su postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE printarr TO printarr;\""

    # Stop PostgreSQL (supervisord will start it properly)
    echo "Stopping temporary PostgreSQL instance..."
    su postgres -c "/usr/lib/postgresql/16/bin/pg_ctl -D $PGDATA stop"

    echo "PostgreSQL initialization complete."
else
    echo "PostgreSQL data directory exists, skipping initialization."
    # Ensure permissions are correct
    chown -R postgres:postgres "$PGDATA"
fi

# Start supervisord in the background to manage PostgreSQL
echo "Starting PostgreSQL via supervisord..."
/usr/bin/supervisord -c /etc/supervisor/conf.d/printarr.conf &
SUPERVISOR_PID=$!

# Wait for PostgreSQL to be ready before running migrations
echo "Waiting for PostgreSQL to accept connections..."
for i in {1..60}; do
    if su postgres -c "/usr/lib/postgresql/16/bin/pg_isready -q -h localhost"; then
        echo "PostgreSQL is ready."
        break
    fi
    if [ $i -eq 60 ]; then
        echo "ERROR: PostgreSQL failed to start within 60 seconds"
        exit 1
    fi
    sleep 1
done

# Run database migrations
echo "Running database migrations..."
cd /app/backend
alembic upgrade head

echo "Starting Printarr services..."
# Wait for supervisord (it's already running and managing services)
wait $SUPERVISOR_PID

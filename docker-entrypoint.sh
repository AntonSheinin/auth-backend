#!/bin/bash
set -e

echo "Running database migrations..."

# Run Alembic migrations
# For new databases, this will create all tables
# For existing databases, it will apply any pending migrations
python -m alembic upgrade head

echo "Migrations complete. Starting application..."

# Execute the main command
exec "$@"

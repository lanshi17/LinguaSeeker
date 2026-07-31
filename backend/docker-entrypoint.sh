#!/bin/bash
set -e

# Run database migrations before starting the server
echo "Running database migrations..."
cd /app
python -m alembic -c database/alembic.ini upgrade head

# Change to backend directory for uvicorn
cd /app/backend

# Start the server
echo "Starting uvicorn server..."
exec "$@"

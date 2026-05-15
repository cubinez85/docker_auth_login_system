#!/bin/bash
set -e
echo "🔧 Initializing database extensions and settings..."
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    SET timezone = 'UTC';
EOSQL
echo "✅ Database initialized successfully"

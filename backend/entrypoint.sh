#!/bin/bash
set -e

echo "=== ADMINCHAT Panel Backend Starting ==="

# Wait for PostgreSQL
echo "Waiting for PostgreSQL..."
while ! python3 -c "
import asyncio, asyncpg, os
async def check():
    url = os.environ.get('DATABASE_URL', '').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(url)
    await conn.close()
asyncio.run(check())
" 2>/dev/null; do
    echo "PostgreSQL not ready, retrying in 2s..."
    sleep 2
done
echo "PostgreSQL is ready!"

# Wait for Redis
echo "Waiting for Redis..."
while ! python3 -c "
import redis, os
r = redis.from_url(os.environ.get('REDIS_URL', 'redis://redis:6379/0'))
r.ping()
" 2>/dev/null; do
    echo "Redis not ready, retrying in 2s..."
    sleep 2
done
echo "Redis is ready!"

# Run database migrations
echo "Running database migrations..."
alembic upgrade head 2>/dev/null || echo "No migrations to run (or first startup)"

# Start the application
echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WORKERS:-1}

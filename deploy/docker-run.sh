#!/bin/bash
# ============================================================
# ADMINCHAT Panel - Docker Run (Standalone)
# ============================================================
# Use this when you already have PostgreSQL and Redis running.
# This only starts the ADMINCHAT backend + frontend containers.
#
# Prerequisites:
#   - PostgreSQL 16+ running and accessible
#   - Redis 7+ running and accessible
#   - A database created for ADMINCHAT
#
# Usage:
#   1. Copy .env.example to .env and configure
#   2. chmod +x docker-run.sh
#   3. ./docker-run.sh
#
# To stop:
#   docker stop adminchat-backend adminchat-frontend
#   docker rm adminchat-backend adminchat-frontend
# ============================================================

set -e

# Load environment variables
if [ ! -f .env ]; then
    echo "ERROR: .env file not found. Copy .env.example to .env and configure it."
    exit 1
fi
source .env

IMAGE_TAG="${IMAGE_TAG:-latest}"
REGISTRY="ghcr.io/fxxkrlab/adminchat_panel"

echo "=== ADMINCHAT Panel - Docker Run ==="
echo "Image tag: ${IMAGE_TAG}"

# Create network if not exists
docker network create adminchat 2>/dev/null || true

# ---- Choose volume type ----
# Option A: Named volumes (recommended, managed by Docker)
MEDIA_VOLUME="adminchat-media"
docker volume create ${MEDIA_VOLUME} 2>/dev/null || true
MEDIA_MOUNT="-v ${MEDIA_VOLUME}:/app/media"

# Option B: Bind mount (uncomment below, comment out Option A)
# mkdir -p ./data/media
# MEDIA_MOUNT="-v $(pwd)/data/media:/app/media"

# ---- Backend ----
echo "Starting backend..."
docker pull ${REGISTRY}-backend:${IMAGE_TAG}
docker rm -f adminchat-backend 2>/dev/null || true
docker run -d \
    --name adminchat-backend \
    --network adminchat \
    --restart unless-stopped \
    --env-file .env \
    ${MEDIA_MOUNT} \
    -p 8000:8000 \
    --health-cmd="curl -f http://localhost:8000/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    ${REGISTRY}-backend:${IMAGE_TAG}

# ---- Frontend ----
echo "Starting frontend..."
docker pull ${REGISTRY}-frontend:${IMAGE_TAG}
docker rm -f adminchat-frontend 2>/dev/null || true
docker run -d \
    --name adminchat-frontend \
    --network adminchat \
    --restart unless-stopped \
    -p 3000:80 \
    ${REGISTRY}-frontend:${IMAGE_TAG}

echo ""
echo "=== ADMINCHAT Panel Started ==="
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo "Health:   http://localhost:8000/health"
echo ""
echo "NOTE: Configure your reverse proxy (Nginx/APISIX/Caddy) to:"
echo "  - Forward /api/* and /ws/* to backend:8000"
echo "  - Forward /* to frontend:3000 (or frontend container port 80)"

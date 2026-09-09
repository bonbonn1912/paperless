#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Deploying Paperless ==="

# Check for .env file
if [ ! -f .env ]; then
    echo "Warning: .env file not found. Copying .env.example..."
    cp .env.example .env
fi

# Pull latest images if configured
echo "Pulling container images..."
docker compose pull || true

# Start or update containers
echo "Starting containers..."
docker compose up -d --remove-orphans

# Health status
echo "Services status:"
docker compose ps

echo "Checking health endpoint..."
sleep 3
if curl -fsSL http://127.0.0.1:${PAPERLESS_PORT:-8088}/health > /dev/null 2>&1; then
    echo "✓ Paperless is up and healthy on 127.0.0.1:${PAPERLESS_PORT:-8088}"
else
    echo "⚠ Waiting for services to initialize. Check logs with: docker compose logs -f"
fi

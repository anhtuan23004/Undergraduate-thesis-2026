#!/bin/bash
set -euo pipefail

# Backup MongoDB and Langfuse data for environment migration
# Usage: ./backup.sh [backup_dir]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="${1:-$PROJECT_ROOT/backups/$(date +%Y%m%d_%H%M%S)}"

MONGO_USER="${MONGO_ROOT_USERNAME:-admin}"
MONGO_PASS="${MONGO_ROOT_PASSWORD:-admin123}"
PG_USER="${POSTGRES_USER:-postgres}"
PG_PASS="${POSTGRES_PASSWORD:-postgres}"
CH_USER="${CLICKHOUSE_USER:-clickhouse}"
CH_PASS="${CLICKHOUSE_PASSWORD:-clickhouse}"

MONGO_COMPOSE="docker compose -p mongodb -f $PROJECT_ROOT/infrastructure/mongodb/docker-compose-mongodb.yml"
LANGFUSE_COMPOSE="docker compose -p langfuse -f $PROJECT_ROOT/infrastructure/langfuse/docker-compose.langfuse.yml"

mkdir -p "$BACKUP_DIR"
echo "==> Backup directory: $BACKUP_DIR"

# --- MongoDB ---
echo "==> Backing up MongoDB (claims database)..."
$MONGO_COMPOSE exec -T mongodb mongodump \
  --username "$MONGO_USER" --password "$MONGO_PASS" \
  --authenticationDatabase admin --db claims \
  --archive > "$BACKUP_DIR/mongo_claims.archive"
echo "    Done: mongo_claims.archive"

# --- Langfuse Postgres ---
echo "==> Backing up Langfuse Postgres..."
$LANGFUSE_COMPOSE exec -T postgres pg_dump -U "$PG_USER" postgres \
  > "$BACKUP_DIR/langfuse_postgres.sql"
echo "    Done: langfuse_postgres.sql"

# --- Langfuse ClickHouse ---
echo "==> Backing up Langfuse ClickHouse (volume copy)..."
$LANGFUSE_COMPOSE stop clickhouse
docker run --rm \
  --volumes-from "$($LANGFUSE_COMPOSE ps -aq clickhouse)" \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/clickhouse_data.tar.gz -C /var/lib/clickhouse .
$LANGFUSE_COMPOSE start clickhouse
echo "    Done: clickhouse_data.tar.gz"

# --- Langfuse MinIO ---
echo "==> Backing up Langfuse MinIO..."
docker run --rm \
  --volumes-from "$($LANGFUSE_COMPOSE ps -aq minio)" \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/minio_data.tar.gz -C /data .
echo "    Done: minio_data.tar.gz"

echo ""
echo "==> Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"

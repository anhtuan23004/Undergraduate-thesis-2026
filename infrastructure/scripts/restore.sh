#!/bin/bash
set -euo pipefail

# Restore MongoDB and Langfuse data from backup
# Usage: ./restore.sh <backup_dir>

if [ -z "${1:-}" ]; then
  echo "Usage: $0 <backup_dir>"
  echo "Example: $0 ./backups/20260519_214500"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
BACKUP_DIR="$(cd "$1" && pwd)"

MONGO_USER="${MONGO_ROOT_USERNAME:-admin}"
MONGO_PASS="${MONGO_ROOT_PASSWORD:-admin123}"
PG_USER="${POSTGRES_USER:-postgres}"
CH_USER="${CLICKHOUSE_USER:-clickhouse}"
CH_PASS="${CLICKHOUSE_PASSWORD:-clickhouse}"

MONGO_COMPOSE="docker compose -p mongodb -f $PROJECT_ROOT/infrastructure/mongodb/docker-compose-mongodb.yml"
LANGFUSE_COMPOSE="docker compose -p langfuse -f $PROJECT_ROOT/infrastructure/langfuse/docker-compose.langfuse.yml"

echo "==> Restoring from: $BACKUP_DIR"
echo "==> Starting infrastructure services..."
$MONGO_COMPOSE up -d mongodb
$LANGFUSE_COMPOSE up -d postgres clickhouse minio redis
echo "    Waiting for services to be healthy..."
sleep 10

# --- MongoDB ---
if [ -f "$BACKUP_DIR/mongo_claims.archive" ]; then
  echo "==> Restoring MongoDB..."
  $MONGO_COMPOSE exec -T mongodb mongorestore \
    --username "$MONGO_USER" --password "$MONGO_PASS" \
    --authenticationDatabase admin \
    --drop --archive < "$BACKUP_DIR/mongo_claims.archive"
  echo "    Done."
fi

# --- Langfuse Postgres ---
if [ -f "$BACKUP_DIR/langfuse_postgres.sql" ]; then
  echo "==> Restoring Langfuse Postgres..."
  $LANGFUSE_COMPOSE exec -T postgres psql -U "$PG_USER" -d postgres \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
  $LANGFUSE_COMPOSE exec -T postgres psql -U "$PG_USER" -d postgres \
    < "$BACKUP_DIR/langfuse_postgres.sql"
  echo "    Done."
fi

# --- Langfuse ClickHouse ---
if [ -f "$BACKUP_DIR/clickhouse_data.tar.gz" ]; then
  echo "==> Restoring ClickHouse..."
  $LANGFUSE_COMPOSE stop clickhouse
  docker run --rm \
    --volumes-from "$($LANGFUSE_COMPOSE ps -q clickhouse)" \
    -v "$BACKUP_DIR":/backup \
    alpine sh -c "rm -rf /var/lib/clickhouse/* && tar xzf /backup/clickhouse_data.tar.gz -C /var/lib/clickhouse"
  $LANGFUSE_COMPOSE start clickhouse
  echo "    Done."
elif [ -f "$BACKUP_DIR/clickhouse_backup.zip" ]; then
  echo "==> Restoring ClickHouse from legacy backup (clickhouse_backup.zip)..."
  $LANGFUSE_COMPOSE exec -T clickhouse clickhouse-client \
    --user "$CH_USER" --password "$CH_PASS" \
    --query "RESTORE ALL FROM Disk('backups', 'clickhouse_backup.zip')"
  echo "    Done."
fi

# --- Langfuse MinIO ---
if [ -f "$BACKUP_DIR/minio_data.tar.gz" ]; then
  echo "==> Restoring MinIO..."
  $LANGFUSE_COMPOSE stop minio
  docker run --rm \
    --volumes-from "$($LANGFUSE_COMPOSE ps -q minio)" \
    -v "$BACKUP_DIR":/backup \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/minio_data.tar.gz -C /data"
  $LANGFUSE_COMPOSE start minio
  echo "    Done."
fi

# --- Start all ---
echo "==> Starting all services..."
$MONGO_COMPOSE up -d
$LANGFUSE_COMPOSE up -d
echo ""
echo "==> Restore complete. Verify with:"
echo "    docker compose ps"
echo "    curl http://localhost:8003/health"
echo "    curl http://localhost:3000"

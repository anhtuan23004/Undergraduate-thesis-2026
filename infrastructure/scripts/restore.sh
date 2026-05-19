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
PG_PASS="${POSTGRES_PASSWORD:-postgres}"
CH_USER="${CLICKHOUSE_USER:-clickhouse}"
CH_PASS="${CLICKHOUSE_PASSWORD:-clickhouse}"

COMPOSE_CMD="docker compose -f $PROJECT_ROOT/docker-compose.yml"

echo "==> Restoring from: $BACKUP_DIR"
echo "==> Starting infrastructure services..."
$COMPOSE_CMD up -d mongodb postgres clickhouse minio redis
echo "    Waiting for services to be healthy..."
sleep 10

# --- MongoDB ---
if [ -f "$BACKUP_DIR/mongo_claims.archive" ]; then
  echo "==> Restoring MongoDB..."
  $COMPOSE_CMD exec -T mongodb mongorestore \
    --username "$MONGO_USER" --password "$MONGO_PASS" \
    --authenticationDatabase admin \
    --drop --archive < "$BACKUP_DIR/mongo_claims.archive"
  echo "    Done."
fi

# --- Langfuse Postgres ---
if [ -f "$BACKUP_DIR/langfuse_postgres.sql" ]; then
  echo "==> Restoring Langfuse Postgres..."
  $COMPOSE_CMD exec -T postgres psql -U "$PG_USER" -d postgres \
    -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" 2>/dev/null || true
  $COMPOSE_CMD exec -T postgres psql -U "$PG_USER" -d postgres \
    < "$BACKUP_DIR/langfuse_postgres.sql"
  echo "    Done."
fi

# --- Langfuse ClickHouse ---
if [ -f "$BACKUP_DIR/clickhouse_backup.zip" ]; then
  echo "==> Restoring ClickHouse from BACKUP..."
  docker cp "$BACKUP_DIR/clickhouse_backup.zip" \
    "$($COMPOSE_CMD ps -q clickhouse)":/var/lib/clickhouse/backups/backup.zip
  $COMPOSE_CMD exec -T clickhouse clickhouse-client \
    --user "$CH_USER" --password "$CH_PASS" \
    --query "RESTORE DATABASE default FROM Disk('backups', 'backup.zip')"
  echo "    Done."
elif [ -f "$BACKUP_DIR/clickhouse_data.tar.gz" ]; then
  echo "==> Restoring ClickHouse from volume tar..."
  $COMPOSE_CMD stop clickhouse
  docker run --rm \
    --volumes-from "$($COMPOSE_CMD ps -q clickhouse)" \
    -v "$BACKUP_DIR":/backup \
    alpine sh -c "rm -rf /var/lib/clickhouse/* && tar xzf /backup/clickhouse_data.tar.gz -C /var/lib/clickhouse"
  $COMPOSE_CMD start clickhouse
  echo "    Done."
fi

# --- Langfuse MinIO ---
if [ -f "$BACKUP_DIR/minio_data.tar.gz" ]; then
  echo "==> Restoring MinIO..."
  $COMPOSE_CMD stop minio
  docker run --rm \
    --volumes-from "$($COMPOSE_CMD ps -q minio)" \
    -v "$BACKUP_DIR":/backup \
    alpine sh -c "rm -rf /data/* && tar xzf /backup/minio_data.tar.gz -C /data"
  $COMPOSE_CMD start minio
  echo "    Done."
fi

# --- Start remaining services ---
echo "==> Starting all services..."
$COMPOSE_CMD up -d
echo ""
echo "==> Restore complete. Verify with:"
echo "    docker compose ps"
echo "    curl http://localhost:8003/health"
echo "    curl http://localhost:3000"

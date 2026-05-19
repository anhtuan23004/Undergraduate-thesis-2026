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

COMPOSE_CMD="docker compose -f $PROJECT_ROOT/docker-compose.yml"

mkdir -p "$BACKUP_DIR"
echo "==> Backup directory: $BACKUP_DIR"

# --- MongoDB ---
echo "==> Backing up MongoDB (claims database)..."
$COMPOSE_CMD exec -T mongodb mongodump \
  --username "$MONGO_USER" --password "$MONGO_PASS" \
  --authenticationDatabase admin --db claims \
  --archive > "$BACKUP_DIR/mongo_claims.archive"
echo "    Done: mongo_claims.archive"

# --- Langfuse Postgres ---
echo "==> Backing up Langfuse Postgres..."
$COMPOSE_CMD exec -T postgres pg_dump -U "$PG_USER" postgres \
  > "$BACKUP_DIR/langfuse_postgres.sql"
echo "    Done: langfuse_postgres.sql"

# --- Langfuse ClickHouse ---
echo "==> Backing up Langfuse ClickHouse..."
$COMPOSE_CMD exec -T clickhouse clickhouse-client \
  --user "$CH_USER" --password "$CH_PASS" \
  --query "BACKUP DATABASE default TO Disk('backups', 'backup.zip')" 2>/dev/null || {
  # Fallback: copy volume directly
  echo "    ClickHouse BACKUP command not available, using volume copy..."
  $COMPOSE_CMD stop clickhouse
  docker run --rm \
    --volumes-from "$($COMPOSE_CMD ps -q clickhouse)" \
    -v "$BACKUP_DIR":/backup \
    alpine tar czf /backup/clickhouse_data.tar.gz -C /var/lib/clickhouse .
  $COMPOSE_CMD start clickhouse
}
# If BACKUP command succeeded, extract the file
if $COMPOSE_CMD exec -T clickhouse test -f /var/lib/clickhouse/backups/backup.zip 2>/dev/null; then
  docker cp "$($COMPOSE_CMD ps -q clickhouse)":/var/lib/clickhouse/backups/backup.zip "$BACKUP_DIR/clickhouse_backup.zip"
  $COMPOSE_CMD exec -T clickhouse rm -f /var/lib/clickhouse/backups/backup.zip
  echo "    Done: clickhouse_backup.zip"
else
  echo "    Done: clickhouse_data.tar.gz"
fi

# --- Langfuse MinIO ---
echo "==> Backing up Langfuse MinIO..."
docker run --rm \
  --volumes-from "$($COMPOSE_CMD ps -q minio)" \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/minio_data.tar.gz -C /data .
echo "    Done: minio_data.tar.gz"

echo ""
echo "==> Backup complete: $BACKUP_DIR"
ls -lh "$BACKUP_DIR"

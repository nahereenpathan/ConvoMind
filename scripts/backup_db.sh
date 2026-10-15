#!/usr/bin/env bash
# ===================================================================
# ConvoMind Automated PostgreSQL Database Backup Script
# Usage: ./scripts/backup_db.sh
# Cron example (Daily at 2:00 AM): 0 2 * * * /path/to/backup_db.sh >> /var/log/convomind_backup.log 2>&1
# ===================================================================

set -eo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/convomind}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
CONTAINER_NAME="${CONTAINER_NAME:-convomind_postgres}"
DB_USER="${POSTGRES_USER:-convo_user}"
DB_NAME="${POSTGRES_DB:-convo_db}"
RETENTION_DAYS="${RETENTION_DAYS:-14}"

mkdir -p "${BACKUP_DIR}"

BACKUP_FILE="${BACKUP_DIR}/convomind_db_${TIMESTAMP}.sql.gz"

echo "[$(date -Iseconds)] Starting PostgreSQL database backup for '${DB_NAME}'..."

docker exec "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" -F c | gzip > "${BACKUP_FILE}"

FILE_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[$(date -Iseconds)] Backup completed successfully: ${BACKUP_FILE} (${FILE_SIZE})"

# Remove backups older than RETENTION_DAYS
echo "[$(date -Iseconds)] Cleaning up backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -type f -name "convomind_db_*.sql.gz" -mtime +"${RETENTION_DAYS}" -delete

echo "[$(date -Iseconds)] Backup routine finished cleanly."

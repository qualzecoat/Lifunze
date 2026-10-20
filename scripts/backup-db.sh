#!/usr/bin/env bash
# Backup database Lifunze (pg_dump dari container db) — pola sama seperti
# backup Rephore di Sirius. Retensi 7 hari. Dijalankan cron harian:
#   0 3 * * * /opt/sirius/compose/lifunze/backup-db.sh
set -euo pipefail

BACKUP_DIR="${LIFUNZE_BACKUP_DIR:-/home/sirius/lifunze-backup}"
COMPOSE_DIR="${LIFUNZE_COMPOSE_DIR:-/opt/sirius/compose/lifunze}"
mkdir -p "$BACKUP_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/lifunze-$STAMP.sql.gz"

cd "$COMPOSE_DIR"
docker compose exec -T db pg_dump -U "${POSTGRES_USER:-lifunze}" "${POSTGRES_DB:-lifunze}" | gzip > "$OUT"

# Retensi: hapus backup lebih tua dari 7 hari
find "$BACKUP_DIR" -name 'lifunze-*.sql.gz' -mtime +7 -delete
echo "Backup selesai: $OUT"

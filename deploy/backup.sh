#!/bin/sh
set -eu
export PGHOST="$POSTGRES_HOST" PGPORT="$POSTGRES_PORT" PGDATABASE="$POSTGRES_DB" PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD"
export TZ="${BACKUP_TIMEZONE:-Europe/Moscow}"
backup_once() {
    umask 077
    mkdir -p "$BACKUP_DIR"
    stamp=$(date -u +%Y%m%dT%H%M%SZ)
    final="$BACKUP_DIR/$stamp.dump"
    temporary="$final.partial"
    if pg_dump --format=custom --no-owner --no-acl --file="$temporary" && pg_restore --list "$temporary" >/dev/null; then
        mv "$temporary" "$final"
        sha256sum "$final" > "$final.sha256"
        printf '{"finished_at":"%s","bytes":%s,"status":"success"}\n' "$stamp" "$(wc -c < "$final")" > "$final.json"
        date +%F > "$BACKUP_DIR/.last-success"
        find "$BACKUP_DIR" -maxdepth 1 -name '*.dump' | sort -r | tail -n +"$((BACKUP_RETENTION + 1))" | while IFS= read -r old; do
            rm -f "$old" "$old.sha256" "$old.json"
        done
        echo "Backup successful: $stamp"
    else
        rm -f "$temporary"
        echo "Backup failed: $stamp" >&2
        return 1
    fi
}
if [ "${1:-}" = once ]; then backup_once; exit; fi
while true; do
    today=$(date +%F)
    last=$(cat "$BACKUP_DIR/.last-success" 2>/dev/null || true)
    if [ "$today" != "$last" ] && [ "$(date +%H:%M)" \> "$BACKUP_TIME" -o "$(date +%H:%M)" = "$BACKUP_TIME" ]; then
        backup_once || true
    fi
    sleep 60
done

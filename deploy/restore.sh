#!/bin/sh
# Creates an explicitly named NEW database. Never drops or replaces a live target.
set -eu
archive=${1:?Usage: restore.sh archive.dump NEW_DATABASE_NAME}
target=${2:?Specify a new target database}
export PGHOST="$POSTGRES_HOST" PGPORT="$POSTGRES_PORT" PGUSER="$POSTGRES_USER" PGPASSWORD="$POSTGRES_PASSWORD"
[ "$target" != "$POSTGRES_DB" ] || { echo 'Use a new target database, never the live database' >&2; exit 1; }
pg_restore --list "$archive" >/dev/null
createdb --template=template0 "$target"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$target" "$archive"
psql -X -v ON_ERROR_STOP=1 --dbname="$target" -c 'SELECT count(*) AS vacancies FROM vacancy; SELECT count(*) AS users FROM app_user;'

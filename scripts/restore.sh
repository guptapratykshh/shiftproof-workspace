#!/bin/sh
# Restore only into a fresh, isolated recovery stack. Never overwrite a running database.
set -eu
source_directory=${1:?Usage: scripts/restore.sh BACKUP_DIRECTORY}
test -f "$source_directory/database.dump"
test -f "$source_directory/evidence.tar.gz"
table_count=$(docker compose exec -T database psql -U shiftproof -d shiftproof -Atc "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
if [ "$table_count" != 0 ]; then printf '%s\n' 'Restore refused: target database must be empty.' >&2; exit 1; fi
docker compose exec -T database pg_restore -U shiftproof -d shiftproof --no-owner --single-transaction < "$source_directory/database.dump"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -xzf - < "$source_directory/evidence.tar.gz"
printf '%s\n' 'Restore finished. Validate records and evidence before directing traffic to this stack.'

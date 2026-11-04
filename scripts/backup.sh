#!/bin/sh
set -eu
umask 077
destination=${1:?Usage: scripts/backup.sh BACKUP_DIRECTORY}
mkdir -p "$destination"
docker compose stop worker api
trap 'docker compose start api worker >/dev/null' EXIT INT TERM
docker compose exec -T database pg_dump -U shiftproof -d shiftproof -Fc > "$destination/database.dump"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -czf - evidence > "$destination/evidence.tar.gz"
printf 'Backup complete: %s\n' "$destination"

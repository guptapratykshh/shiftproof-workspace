#!/bin/sh
set -eu
umask 077
destination=${1:?Usage: scripts/backup.sh BACKUP_DIRECTORY}
mkdir -p "$destination"
docker compose stop worker api
trap 'docker compose start api worker >/dev/null' EXIT INT TERM
test ! -e "$destination/database.tar.gz"
docker compose run --rm --no-deps -T --entrypoint sh api -c 'python -m app.mongo_backup backup /tmp/database.tar.gz >&2 && cat /tmp/database.tar.gz' > "$destination/database.tar.gz"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -czf - evidence > "$destination/evidence.tar.gz"
printf 'Backup complete: %s\n' "$destination"

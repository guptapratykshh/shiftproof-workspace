#!/bin/sh
# Restore only into a fresh, isolated recovery stack. Never overwrite a running database.
set -eu
source_directory=${1:?Usage: scripts/restore.sh BACKUP_DIRECTORY}
test -f "$source_directory/database.tar.gz"
test -f "$source_directory/evidence.tar.gz"
docker compose stop api worker
docker compose run --rm --no-deps -T --entrypoint sh api -c 'cat > /tmp/database.tar.gz && python -m app.mongo_backup restore /tmp/database.tar.gz' < "$source_directory/database.tar.gz"
docker compose run --rm --no-deps -T --entrypoint tar api -C /app/data -xzf - < "$source_directory/evidence.tar.gz"
printf '%s\n' 'Restore finished. Validate records and evidence before directing traffic to this stack.'

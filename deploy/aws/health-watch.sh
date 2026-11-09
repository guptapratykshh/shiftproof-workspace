#!/usr/bin/env bash
set -euo pipefail
cd /opt/shiftproof/current
exec 9>/opt/shiftproof/health.lock
flock -n 9 || exit 0
compose=(docker compose --env-file .env.production --project-directory . -f deploy/aws/compose.yaml)
for service in api worker web; do
  container=$("${compose[@]}" ps -a -q "$service")
  if [ -z "$container" ]; then
    "${compose[@]}" up -d "$service"
  elif [ "$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$container")" = unhealthy ]; then
    logger -t shiftproof "Restarting unhealthy service: $service"
    "${compose[@]}" restart "$service"
  fi
done

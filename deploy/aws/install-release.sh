#!/usr/bin/env bash
# Invoked through Systems Manager. Arguments are non-secret S3 object names.
set -euo pipefail
umask 077
bucket=$1
release=$2
region=${3:-ap-south-1}
root=/opt/shiftproof
mkdir -p "$root/releases/$release"
exec 9>"$root/health.lock"
flock -w 900 9
previous=$(readlink -f "$root/current" || true)
aws s3 cp "s3://$bucket/releases/$release.tar.gz" "$root/release.tar.gz" --region "$region" --only-show-errors
tar -xzf "$root/release.tar.gz" -C "$root/releases/$release"
aws ssm get-parameter --name /shiftproof/production/environment --with-decryption --region "$region" --query Parameter.Value --output text > "$root/releases/$release/.env.production"
printf '\nRELEASE_ID=%s\n' "$release" >> "$root/releases/$release/.env.production"
chmod 600 "$root/releases/$release/.env.production"
cd "$root/releases/$release"
compose=(docker compose --env-file .env.production --project-directory . -f deploy/aws/compose.yaml)
"${compose[@]}" config --quiet
if ! "${compose[@]}" build api web > "$root/build-$release.log" 2>&1; then
  tail -n 60 "$root/build-$release.log"
  exit 1
fi
# Avoid hundreds of redundant Atlas index commands for releases with no schema
# changes. Changed schema/bootstrap code still runs before replacing the API.
schema_hash() {
  python3 - "$1" <<'PY'
import hashlib, sys
from pathlib import Path
root = Path(sys.argv[1])
files = list((root / 'backend/app/models').rglob('*.py'))
files += [root / 'backend/app/mongo.py', root / 'backend/app/bootstrap.py']
digest = hashlib.sha256()
for path in sorted(files):
    digest.update(str(path.relative_to(root)).encode())
    digest.update(path.read_bytes())
print(digest.hexdigest())
PY
}
if [ -z "$previous" ] || [ "$(schema_hash "$previous")" != "$(schema_hash "$PWD")" ]; then
  "${compose[@]}" run --rm --no-deps migrate
fi
rollback() {
  if [ -n "$previous" ] && [ "$previous" != "$PWD" ]; then
    logger -t shiftproof "Release $release failed; restoring the previous containers"
    docker compose --env-file "$previous/.env.production" --project-directory "$previous" \
      -f "$previous/deploy/aws/compose.yaml" up -d --no-deps --wait --wait-timeout 360 api worker web scanner-updates || true
  fi
}
trap rollback ERR
"${compose[@]}" up -d --no-deps --wait --wait-timeout 360 api worker web scanner-updates
ln -sfn "$root/releases/$release" "$root/current"
trap - ERR
install -m 700 deploy/aws/health-watch.sh "$root/health-watch.sh"
install -m 700 deploy/aws/backup.sh "$root/backup.sh"
cat > /etc/systemd/system/shiftproof-health.service <<'UNIT'
[Unit]
Description=Restart unhealthy ShiftProof containers
After=docker.service
[Service]
Type=oneshot
ExecStart=/opt/shiftproof/health-watch.sh
UNIT
cat > /etc/systemd/system/shiftproof-health.timer <<'UNIT'
[Unit]
Description=Check ShiftProof services every two minutes
[Timer]
OnBootSec=5min
OnUnitActiveSec=2min
[Install]
WantedBy=timers.target
UNIT
cat > /etc/systemd/system/shiftproof-backup.service <<'UNIT'
[Unit]
Description=Create an encrypted off-host ShiftProof database backup
After=docker.service
[Service]
Type=oneshot
ExecStart=/opt/shiftproof/backup.sh
UNIT
cat > /etc/systemd/system/shiftproof-backup.timer <<'UNIT'
[Unit]
Description=Daily ShiftProof snapshot
[Timer]
OnCalendar=*-*-* 21:00:00 UTC
Persistent=true
RandomizedDelaySec=300
[Install]
WantedBy=timers.target
UNIT
systemctl daemon-reload
systemctl enable --now shiftproof-health.timer shiftproof-backup.timer
rm -f "$root/release.tar.gz"
"${compose[@]}" ps --format json

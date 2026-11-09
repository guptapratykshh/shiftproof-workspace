#!/usr/bin/env bash
set -euo pipefail
cd /opt/shiftproof/current
exec 9>/opt/shiftproof/backup.lock
flock -n 9 || exit 0
docker compose --env-file .env.production --project-directory . -f deploy/aws/compose.yaml exec -T worker python - <<'PY'
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from app.db import engine
from app.mongo_backup import backup
from app.config import get_settings
from app.services.storage import s3

stamp = datetime.now(UTC).strftime('%Y-%m-%dT%H-%M-%SZ')
with TemporaryDirectory() as folder:
    archive = Path(folder) / 'database.tar.gz'
    # Atlas snapshot sessions keep every collection at the same point in time.
    with engine.client.start_session(snapshot=True) as session:
        result = backup(engine.database, archive, session=session)
    s3().upload_file(str(archive), get_settings().s3_bucket, f'backups/{stamp}.tar.gz',
                     ExtraArgs={'ServerSideEncryption': 'AES256'})
print({'backup': stamp, **result})
PY

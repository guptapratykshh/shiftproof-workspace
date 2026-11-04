# Local operation and deployment preparation

The user chose local-only operation for this delivery. The files here prepare a future deployment; no server, paid resource or public deployment has been created. Existing private Sites hosting retains its access settings and previous frontend version.

## Native local development

From the repository root:

```sh
npm ci
cd backend
uv sync --frozen
# Optional: cp .env.example .env, then edit locally.
cd ..
npm run dev:full
```

Frontend: http://localhost:5173. API health: http://127.0.0.1:8000/api/v1/health. API schema: http://127.0.0.1:8000/docs. The launcher migrates before starting the API, worker and Vite proxy, and stops its child processes on Ctrl+C. FFmpeg/ffprobe must be on PATH for media. Local text workflows need no provider credentials.

`backend/data/` contains the SQLite database, private evidence and captured development email. Treat it as private user data. There is no default account. Register, read the local verification email, complete required setup, activate your supervisor, then create/activate workers. Finish onboarding before assigning work. The tests use their own temporary databases and do not provision the development workspace.

If you prefer separate terminals, run `uv run alembic upgrade head`, `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`, and `uv run python -m app.worker` from `backend/`; start Vite from the root with `VITE_API_BASE_URL=/api/v1 npm run dev`.

## Container development stack

Requires Docker Engine/Desktop/Colima running with current Docker Compose v2 or later:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

The stack contains PostgreSQL 17, a one-shot Alembic migration, the unprivileged Python API, a separate background worker, nginx serving the React build, and Mailpit. Frontend and captured email bind loopback on ports 8080 and 8025. Database and API ports remain internal. Named volumes persist data and evidence. `docker compose down` stops services while retaining volumes; do not add `-v` unless deliberately deleting all local data.

These compose files were parsed successfully. **The Docker daemon was unavailable in the implementation environment, so image builds, container startup and TLS issuance have not been verified here.** Native API/frontend execution and PostgreSQL migrations/workflows/restore have been tested independently.

## Future HTTPS deployment

1. Prepare a private Linux host with Docker/Compose, a DNS name pointing to it, inbound ports 80/443 and enough disk for database/evidence/backups.
2. Copy `deploy/production.env.example` to root `.env`; replace every placeholder and protect it with `chmod 600 .env`. Use a long random URL-safe PostgreSQL password because it is interpolated in a database URL. Configure your real SMTP sender and provider keys privately.
3. Choose private local storage or a private encrypted object bucket. Configure and verify the PDF scanner if PDF evidence is required. The image has ClamAV binaries; updated definitions need a maintained read-only mount.
4. Build/validate the merged configuration and then start it when deployment is authorized:

```sh
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

The production override forces production mode, Secure cookies, an HTTPS frontend/origin and external SMTP; required domain, database password and SMTP host must be supplied. It removes the direct frontend port and disables Mailpit. Caddy terminates TLS and proxies nginx. API settings reject SQLite, insecure cookies and file mail mode in production.

Inspect service health and redacted logs, verify HTTPS/security headers, register your own account, check email delivery, complete setup, and run the role/tenant/critical-task/report/handover acceptance flows before directing users to it. Health provider booleans mean a key is configured, not that the provider has passed a live check. Queue failure counts are visible in health; administrators have a scoped job-status page. A healthy API does not by itself prove that the worker or mail provider is healthy.

Never upload backend `.env`, the database or private media to a static hosting artifact. Sites serves the public frontend only; the full Python/PostgreSQL stack needs its own hosting or this local setup.

## Build and migration operations

`npm run build` typechecks and produces `dist/`, including a static-only offline cache manifest. Docker builds set `VITE_API_BASE_URL=/api/v1`. A manual connected frontend build uses `VITE_API_BASE_URL=/api/v1 npm run build`. With that value absent, the generated static frontend explicitly shows unavailable API behavior.

`uv run alembic upgrade head` applies versioned changes. The migration chain includes database-enforced append-only history. The QA script exercises upgrade → downgrade → upgrade on isolated databases. Do not downgrade a populated production database without a reviewed data/recovery plan; schema rollback is not a substitute for recovering user data.

## Backups and recovery

Database rows and private evidence must be captured together. `scripts/backup.sh DIRECTORY` pauses API/worker writes, takes a PostgreSQL custom-format dump, archives the local evidence volume, and restarts services via a shell trap. The directory is created under restrictive permissions. The frontend may show temporary service unavailability while writes are paused. Keep copies off-host with access control/encryption, retention and regular restore drills.

For the production stack, select its compose files through the environment when invoking scripts:

```sh
COMPOSE_FILE=compose.yaml:compose.production.yaml sh scripts/backup.sh /private/backup-directory
```

To restore, use a **fresh isolated compose project** with an empty database and separate volumes. Start only its database, build the API image, then run `scripts/restore.sh DIRECTORY` in that project's environment. The script refuses any target containing public-schema tables, restores the dump in a transaction and restores the matching evidence archive. Start migrate/API/worker/web afterward. Verify organization counts, immutable history and sample evidence checksums before directing traffic to the recovery stack. Do not use production ports concurrently with a recovery stack; use separate development ports or an isolated host.

The scripts back up local-volume evidence. If S3 is selected, back up/version the private bucket separately and recover it to the matching database point. Never assume the local evidence archive includes S3 objects. Native SQLite backups require stopping `dev:full` and copying the whole `backend/data` directory together; do not copy only a live `.db` file while its WAL is active.

`backend/tests/verify_postgres_restore.py` has been run against a local PostgreSQL 17 maintenance connection. It creates two temporary uniquely named databases, migrates up/down/up, verifies history UPDATE/DELETE rejection, inserts test records, performs real `pg_dump`/`pg_restore`, restores a paired evidence archive and checks its checksum. It drops only its own temporary QA databases. This validates the recovery mechanics, not your eventual host's backup schedule or S3 lifecycle policy.

```sh
# Dedicated local QA cluster only; requires PostgreSQL CLI tools and create-database rights.
cd backend
PYTHONPATH=. PG_QA_DSN=postgresql://USER@127.0.0.1:PORT/postgres \
  uv run python tests/verify_postgres_restore.py
```

## Verification commands

```sh
npm run build
npm test
npm run test:workspace
cd backend
uv run pytest -q
TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:PORT/TEST_DATABASE \
  uv run pytest -q
```

The browser tests use installed Google Chrome and private fixture data. The workspace suite owns ports 5175/8001 and `/tmp/shiftproof-browser-qa`; the public suite uses 4173. Dedicated test schemas/databases are removed by fixtures. Review captures are generated under `test-results/` and copied to `artifacts/review/` for delivery.

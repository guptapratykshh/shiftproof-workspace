# Operation and deployment

The full application is hosted on AWS at **https://13.203.164.49**, independently of the local Mac. MongoDB Atlas remains the primary structured-data store. See [the AWS runbook](aws-deployment.md) for the deployed architecture, releases, backups, security checks and recovery. The local and generic Compose alternatives below remain available for development.

## Native local development

From the repository root:

```sh
npm ci
cd backend
uv sync --frozen
# Copy .env.example to .env if absent, then configure DATABASE_URL privately.
cd ..
npm run dev:full
```

Frontend: http://localhost:5173. API health: http://127.0.0.1:8000/api/v1/health. API schema: http://127.0.0.1:8000/docs. The launcher migrates before starting the API, worker and Vite proxy, and stops its child processes on Ctrl+C. FFmpeg/ffprobe must be on PATH for media. Local text workflows need no provider credentials.

`backend/data/` contains private evidence, captured development email and any retained legacy SQLite backup. Active application records live in the MongoDB database selected by `DATABASE_URL`. A replica set or Atlas cluster is required for transactions. Treat it as private user data. There is no default account. Register, read the local verification email, complete required setup, activate your supervisor, then create/activate workers. Finish onboarding before assigning work. The tests use their own temporary databases and do not provision the development workspace.

If you prefer separate terminals, run `uv run python -m app.bootstrap`, `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --no-access-log`, and `uv run python -m app.worker` from `backend/`; start Vite from the root with `VITE_API_BASE_URL=/api/v1 npm run dev`.

## Container development stack

Requires Docker Engine/Desktop/Colima running with current Docker Compose v2 or later:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Set the external MongoDB `DATABASE_URL` privately in the root `.env` first. The stack contains a one-shot MongoDB schema bootstrap, the unprivileged Python API, a separate background worker, nginx serving the React build, and Mailpit. Frontend and captured email bind loopback on ports 8080 and 8025. The API port remains internal. Database access uses the configured Atlas connection; the named evidence volume stores private media. `docker compose down` stops services while retaining volumes; do not add `-v` unless deliberately deleting all local data.

The AWS-specific Compose configuration, both production images and browser-trusted TLS have been exercised on the live Linux host. The generic development/Caddy configuration below is separate from that deployed configuration.

## Alternative domain-based HTTPS deployment

1. Prepare a private Linux host with Docker/Compose, a DNS name pointing to it, inbound ports 80/443 and enough disk for database/evidence/backups.
2. Copy `deploy/production.env.example` to root `.env`; replace every placeholder and protect it with `chmod 600 .env`. Set `DATABASE_URL` to the intended dedicated MongoDB database, use a restricted database account, and allow the host in Atlas network access. URL-encode special characters in credentials. Configure your real SMTP sender and provider keys privately.
3. Choose private local storage or a private encrypted object bucket. Configure and verify the PDF scanner if PDF evidence is required. The image has ClamAV binaries; updated definitions need a maintained read-only mount.
4. Build/validate the merged configuration and then start it when deployment is authorized:

```sh
docker compose -f compose.yaml -f compose.production.yaml config --quiet
docker compose -f compose.yaml -f compose.production.yaml up -d --build
```

The production override forces production mode, Secure cookies, an HTTPS frontend/origin and external SMTP; required domain, MongoDB URL and SMTP host must be supplied. It removes the direct frontend port and disables Mailpit. Caddy terminates TLS and proxies nginx. API settings reject SQLite, insecure cookies and file mail mode in production.

Inspect service health and redacted logs, verify HTTPS/security headers, register your own account, check email delivery, complete setup, and run the role/tenant/critical-task/report/handover acceptance flows before directing users to it. Health provider booleans mean a key is configured, not that the provider has passed a live check. Queue failure counts are visible in health; administrators have a scoped job-status page. A healthy API does not by itself prove that the worker or mail provider is healthy.

Never upload backend `.env`, the database or private media to a static hosting artifact. Sites serves the public frontend only; the full Python/MongoDB stack needs its own hosting or this local setup.

## Build and migration operations

`npm run build` typechecks and produces `dist/`, including a static-only offline cache manifest. Docker builds set `VITE_API_BASE_URL=/api/v1`. A manual connected frontend build uses `VITE_API_BASE_URL=/api/v1 npm run build`. With that value absent, the generated static frontend explicitly shows unavailable API behavior.

`uv run python -m app.bootstrap` initializes or updates MongoDB validators and indexes without deleting records. MongoDB bootstrap does not run SQL Alembic migrations. SQL migrations remain available for legacy databases and test fixtures.

For a one-time SQL import, stop the API and worker and take a consistent database/evidence backup first. Set the target MongoDB URL privately in the environment, then run from `backend/`:

```sh
uv run python -m app.migrate_to_mongo --source sqlite:////PRIVATE/PATH/backup.db --dry-run
uv run python -m app.migrate_to_mongo --source sqlite:////PRIVATE/PATH/backup.db
```

The importer preserves IDs and validates record counts and SHA-256 fingerprints for every mapped collection. A target with unrelated data is refused; an identical interrupted import can resume without overwriting changed records. Only enable the MongoDB application after the final status is `verified`. Keep the source backup for recovery. After new MongoDB writes occur, reverting to the old SQL backup would lose those new writes; it is not a synchronization mechanism.

## Backups and recovery

Database records and private evidence must be captured together. `scripts/backup.sh DIRECTORY` pauses the Compose API/worker, exports all MongoDB collections as BSON with validators, indexes, counts and SHA-256 hashes, archives the local evidence volume, and restarts services via a shell trap. Backups contain private data: use an access-controlled directory, encrypt off-host copies, and run restore drills. No other application process may write to that database during the backup.

```sh
COMPOSE_FILE=compose.yaml:compose.production.yaml sh scripts/backup.sh /private/backup-directory
```

Restore into a **fresh isolated Compose project**, with a separate empty MongoDB database configured in its private `.env` and a separate evidence volume. Build the API image, then run `scripts/restore.sh DIRECTORY`. The script stops API/worker, refuses nonempty databases, verifies all archive hashes before writing, restores the database and paired evidence archive, and leaves services stopped for review. A failed partial restore should be inspected and retried against a new empty target. Start bootstrap/API/worker/web only after the restore is verified. Never use the active database as a restore target.

For a native local backup, stop the full launcher and run `uv run python -m app.mongo_backup backup /private/database.tar.gz` from `backend/`, paired with an archive of `backend/data/evidence`. For recovery, set `DATABASE_URL` to a fresh isolated database, then run `uv run python -m app.mongo_backup restore /private/database.tar.gz`. Restore refuses any database that already has collections. Atlas-managed backups may be used in addition to these exports, depending on the cluster tier and configuration.

The scripts include local-volume evidence only. If S3 is selected, back up/version the private bucket separately and recover it to the matching database point. MongoDB migration does not move media files into Atlas.

## Verification commands

```sh
npm run build
npm test
npm run test:workspace
cd backend
uv run pytest -q
# Export DATABASE_URL and TEST_DATABASE_URL privately to the same empty
# shiftproof_test_<unique suffix> database before the MongoDB integration run.
uv run pytest -q
```

The browser tests use installed Google Chrome and private fixture data. The workspace suite owns ports 5175/8001 and `/tmp/shiftproof-browser-qa`; the public suite uses 4173. Dedicated test schemas/databases are removed by fixtures. Review captures are generated under `test-results/` and copied to `artifacts/review/` for delivery.

# ShiftProof

ShiftProof is a local, full-stack shift-handover application with organization administrator, supervisor and worker workspaces. It preserves the supplied landing/sign-in composition and shared plum/lavender theme, and connects the operational screens to a Python API and persistent database.

The full app runs locally with a MongoDB Atlas database. An optional temporary public tunnel forwards the local frontend and API; it requires the Mac and local processes to stay running. The existing private Sites frontend is separate.

## Start the full application

Requirements: Node.js 22.12+, Python 3.12+, [uv](https://docs.astral.sh/uv/), and FFmpeg/ffprobe for audio/video. Google Chrome is required by the browser tests. Use the committed npm and uv lockfiles.

```sh
npm ci
cd backend
uv sync --frozen
# Copy .env.example to .env and configure DATABASE_URL privately.
cd ..
npm run dev:full
```

Open **http://localhost:5173**. This command initializes MongoDB collections, validators and indexes, then starts the frontend, API on port 8000, and background worker. Stop all three with Ctrl+C. Set `DATABASE_URL` in `backend/.env` to your MongoDB replica-set/Atlas connection, selecting the `shiftproof` database. Application records are stored directly through PyMongo; SQLite is retained only for legacy imports and isolated regression tests. Do not run two full development launchers against the same ports.

Create your own organization at `/signup`. Registration queues a verification link before creating the organization. With the default `MAIL_MODE=file`, the background worker writes private `.eml` messages to `backend/data/outbox/`. Open the newest message locally and follow its link; the confirmation screen identifies this local-only mode. For real inbox delivery, configure SMTP privately in `backend/.env` and restart the API and worker; see [email setup](docs/integrations.md#email). SMTP confirmation means queued for delivery, not confirmed inbox placement. No shared demo login is installed.

Complete the first five setup steps: organization profile/timezone, departments, teams, shifts, and an **activated** primary supervisor. Supervisor invitations use the same outbox. Worker creation provides a private activation link; the worker chooses their own six-digit PIN. PINs are never shown to managers.

Database and optional provider settings belong in `backend/.env` (copy `backend/.env.example`). Frontend-only `npm run dev` intentionally reports unavailable authentication when `VITE_API_BASE_URL` is unset. `dev:full` sets it to `/api/v1` automatically.

## What is included

- Screenshot-aligned landing, role selection, registration, individual login, recovery and activation; eight organization types; a one-click sun/moon icon switches between persistent dark/light themes on every page, with English/Hindi interface support.
- Resumable organization setup, departments/teams, supervisor invitations and independent department permissions, primary/backup coverage, shift definitions/assignments, weekly coverage, policies and temporary administrative takeovers.
- Workforce creation, email-free worker activation, CSV/XLSX validation/preview/confirmation, qualifications/expiry, absence records and corrections, assignment eligibility and PIN recovery.
- Individual/shared-team tasks, list/board/calendar views, optional priority, mandatory critical approval, dependencies, comments/evidence, reassignment/history, templates, recurring routine allocation and completion verification.
- Voice/text report composition, consent, encrypted local drafts, account-bound idempotent synchronization, immutable corrections, private evidence, original transcript/AI suggestion/human confirmation separation, neutral clarification and conflict decisions.
- Immediate safety alerts, acknowledgement, investigation, corrective work, resolution and escalation; linked cross-department follow-ups retain their origin and access boundaries.
- Draft/published/provisional handovers, immutable versions and comparisons, incoming-shift routing, overall receipt and individual critical-item acknowledgements, reminders and optional audio generation.
- Distinct role dashboards, actual-record analytics, date/scope filters, charts/CSV export, notifications and live updates, account preferences/sessions, audit history and background-job status.

[Feature coverage](docs/coverage.md) maps requirements to code and verification. The detailed inventories in `docs/requirements-roles.md` and `docs/requirements-workflows.md` are source checklists, not a claim that every individual design detail has received acceptance sign-off.

## External services and limitations

Gnani Prisma speech-to-text, Gnani Timbre handover audio and Gemini extraction adapters are implemented with bounded jobs, validation and explicit failure states. **Live provider calls have not been verified without credentials.** Text reporting and written handovers work independently. Configure keys privately; never put them in `VITE_` variables.

PDF evidence requires a working malware scanner. Without one, PDF upload is explicitly unavailable; validated photos and audio/video remain supported. Production SMTP and optional private S3 storage also require your configuration and live checks. See [integrations](docs/integrations.md).

Offline editing works within an authenticated session with its encryption key in memory. A full reload while offline requires reconnection/sign-in to unlock drafts. This protects shared devices; it does not pretend that offline authentication succeeds. Tasks remain server-authoritative. The service worker caches static assets only.

## Verification

```sh
npm run build
npm test
npm run test:workspace
# Also verify the production offline shell:
SHIFTPROOF_BUILD_TEST=1 npm run test:workspace
cd backend
uv run pytest -q
```

The public browser suite checks ten routes at 320, 390, 768, 900, 1169 and 1600px, both themes and languages, preferences, keyboard controls, validation and unavailable API states. The workspace suite starts an isolated real API/database and exercises task approval, offline sync/account isolation, role pages, critical reporting and handover receipts. Browser fixture accounts exist only in that isolated test database. Final desktop/mobile images are collected in the [review gallery](artifacts/review/index.html).

The [validation record](docs/validation.md) lists the completed checks and remaining external setup.

MongoDB verification uses `DATABASE_URL` and `TEST_DATABASE_URL` pointing to the same empty `shiftproof_test_<unique suffix>` database. Fixtures refuse other names and delete that test database afterward. Without `TEST_DATABASE_URL`, regression tests use temporary SQLite databases. Never point test tools at the application database. Backup/restore verification is described in [deployment](docs/deployment.md).

## Deployment preparation

```sh
# API + worker + frontend + captured development email, using external MongoDB
# Set DATABASE_URL privately in the root .env for Docker Compose.
# Requires a running Docker daemon.
docker compose up -d --build
```

Open http://localhost:8080 and development mail at http://localhost:8025. The API stays internal; MongoDB uses its configured TLS connection. Production adds the HTTPS override and real mail/storage configuration; see [deployment](docs/deployment.md) before using it. Docker configuration has been checked, but a container build/run is not claimed because the Docker daemon was unavailable during this delivery.

Source layout: `src/pages/workspace/` contains role screens, `src/styles.css` shared tokens/components, `backend/app/api/` endpoints, `backend/app/services/` business rules, `backend/app/models/` shared schema, `backend/app/mongo.py` native persistence, `backend/migrations/` legacy SQL migrations, and `backend/app/worker.py` durable jobs. See [architecture and decisions](docs/architecture.md).

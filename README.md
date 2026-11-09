# ShiftProof

**Work changes hands. The details shouldn't.**

ShiftProof helps manufacturing teams carry clear, traceable updates from one shift to the next. Workers can speak in Hindi, Hinglish or English, check what was understood, and send a report. Supervisors can review conflicting counts, follow up on unfinished work, and publish a handover that keeps the original evidence close.

[Open the live app](https://shiftproof.duckdns.org) · [Demo walkthrough](#demo-walkthrough) · [Deployment guide](docs/aws-deployment.md) · [Voice validation](docs/voice-contradiction-dialogue.md)

## Live deployment

The frontend, Python API and background worker run on AWS in Mumbai. The app stays available when the development Mac is closed. MongoDB Atlas stores application records, and a private S3 bucket stores recordings and attachments.

HTTPS renewal, health checks, service restarts and daily database backups are configured. A backup was restored into an isolated database and checked before that test database was removed. This is a single-server deployment, so releases and host maintenance can briefly interrupt access. The [AWS runbook](docs/aws-deployment.md) covers costs, releases, recovery and verification results.

Sign in with an account created or invited by your organization, or use **Take a demo** to open organization signup. Account credentials are not published in this repository. Real email is queued through SMTP; a queued message does not guarantee inbox delivery.

## Demo walkthrough

The submission follows a simple question: manufacturing reports 100 pieces, but receiving counts only 85. What happened to the other 15?

1. **Set up the workplace.** The owner adds departments, teams, shifts and supervisors, then creates worker accounts. A directional Manufacturing → Receiving link allows the two departments to compare related transfers.
2. **Record the first update.** Worker A reports 100 manufactured pieces for batch B12 and transfer MOVE-1.
3. **Check the next update.** Worker B says they received 85 pieces for the same transfer. Gnani Prisma transcribes the recording. ShiftProof extracts the relevant facts and checks the matching reports.
4. **Ask about the difference.** Gnani Timbre speaks a short clarification question. The same question appears on screen. B can reply by voice, type an answer, repeat the question, or say they are unsure.
5. **Confirm and send.** If B explains that 15 pieces remain in manufacturing, the received count stays at 85 and the explanation stays with the report. B reviews it and taps **Confirm and send**.
6. **Verify and hand over.** A receives a clarification request, and the responsible supervisors receive a notification. A supervisor reviews the evidence and records a decision. The next shift can read or listen to the published handover and confirm receipt.

The app also checks changes in a worker's own reports. For counts such as 75 and 80 packed products, it asks whether they describe the same work and reporting period before treating them as a possible mismatch. Different batches, units, additional production and partial deliveries need different interpretations.

A worker's spoken answer never submits a report or resolves a conflict. Original statements remain in the history. After at most three clarification questions, the worker can review the report with any uncertainty still visible.

## Three workspaces

| Role | What they do |
| --- | --- |
| Organization owner | Set up departments, teams, shifts and policies; manage workforce access and supervisor coverage; review analytics and audit history. |
| Supervisor | Assign and verify work, review reports and evidence, investigate alerts, resolve discrepancies and publish handovers. |
| Worker | See assigned tasks, speak or type an update, answer clarification requests, save a draft and acknowledge incoming handovers. |

The interface supports English and Hindi. A single sun or moon button switches between light and dark themes. Pages adapt to mobile, tablet and desktop screens.

## Voice and everyday work

- **Gnani Prisma:** speech recognition for short worker updates, with a 29-second recording limit.
- **Gnani Timbre:** spoken clarification questions and handover playback.
- **Structured reports:** quantities, batches, equipment, quality conditions and task status stay linked to the source transcript and human confirmation.
- **Tasks:** individual and team assignments, list/board/calendar views, dependencies, recurring work, evidence and completion checks.
- **Safety and follow-ups:** immediate supervisor alerts, investigations, corrective work and linked requests between departments.
- **Handovers:** drafts, published versions, pending conditions, incoming-shift routing and separate acknowledgements for critical items.
- **Workforce:** invitations, worker activation, import previews, qualifications, absences and assignment eligibility.
- **Offline drafts:** encrypted drafts on the device, account isolation and idempotent synchronization when the connection returns.

Provider failures are shown clearly. Workers can keep their recording or type an update when speech processing is unavailable. An incomplete check is never presented as proof that reports agree.

## Evidence and human review

Reports keep the original transcript, suggested fields, confirmed values and later corrections separate. Comparisons use work identifiers, reporting periods, units and counting basis. A difference between manufactured and received quantities is a transfer question to investigate, not proof that either worker is wrong.

Cross-department questions share only the relevant operational facts. Full reports and recordings remain subject to role and department permissions. Acknowledging a handover confirms receipt; it does not complete a task or resolve an issue.

The submission walkthrough uses sample operational data. Recorded demonstration shots and live-provider checks are documented separately, so a staged recording is not presented as a live speech test. See the [voice validation record](docs/voice-contradiction-dialogue.md) and [AWS verification results](docs/aws-deployment.md#validation-record).

## Run locally

Requirements: Node.js 22.12+, Python 3.12+, [uv](https://docs.astral.sh/uv/), and FFmpeg/ffprobe. Browser tests use Google Chrome. Use the committed lockfiles.

```sh
npm ci
cd backend
uv sync --frozen
# If .env is absent, copy .env.example to .env and configure it privately.
cd ..
npm run dev:full
```

Open **http://localhost:5173**. The launcher initializes the database and starts the frontend, API on port 8000, and worker. Ctrl+C stops its child processes. Avoid running two launchers on the same ports.

Use a separate development database in `backend/.env`, with a MongoDB replica set or Atlas connection. Set a distinct `JOB_NAMESPACE`, such as `dev`, if multiple runtimes share a database. Application records use MongoDB; SQLite is retained for isolated tests and legacy imports. Do not use the production database for test fixtures.

For development, `MAIL_MODE=file` writes verification and invitation messages to the private `backend/data/outbox/` directory. The worker must be running. For inbox delivery, configure SMTP as described in [email setup](docs/integrations.md#email).

Register an organization, verify its email, then complete the profile, departments, teams, shifts and primary-supervisor setup. Supervisors activate their invitations. Workers use their activation link to choose a private six-digit PIN.

The full launcher configures `/api/v1` automatically. A standalone connected frontend needs `VITE_API_BASE_URL=/api/v1`; without it, authentication shows that the API is unavailable. Keep provider and database credentials in backend configuration, never in `VITE_` variables or Git.

## Verification

```sh
# Connected production build
VITE_API_BASE_URL=/api/v1 npm run build

# Public pages
npm test

# Workspace flows, including the production offline shell
SHIFTPROOF_BUILD_TEST=1 STORAGE_MODE=local S3_KEY_PREFIX='' npm run test:workspace

# Dedicated voice conversation fixtures
STORAGE_MODE=local S3_KEY_PREFIX='' npx playwright test --config playwright.dialogue.config.ts

# Backend regression suite
cd backend
uv run pytest -q
```

The 9 November AWS release passed 191 backend tests. Six optional integration tests were skipped in that standard run; isolated MongoDB and live speech checks were run separately. Public-page, workspace, contradiction and dedicated voice browser checks passed, including the 100/85 workflow and the 75/80 scope question. See the [full validation record](docs/aws-deployment.md#validation-record) for retries, test boundaries and results.

Browser checks cover widths from 320 to 2560 CSS pixels, both themes and languages, keyboard controls, form errors and role workflows. Test accounts are created in isolated databases. MongoDB browser fixtures require a fresh `shiftproof_test_browser_<unique suffix>` database; native database tests use `shiftproof_test_<unique suffix>`. The fixtures reject other names and clean up their databases.

## Operations and current limits

- The AWS app uses private S3 storage, a PDF malware scanner, secure cookies and instance-role access. Provider settings are kept in encrypted configuration.
- Offline drafts can be edited while the authenticated session retains its encryption key. A full reload while offline requires reconnection and sign-in to unlock them. Static assets are cached; account data is not.
- Safety alerts can be sent without waiting for AI checks. They do not replace the workplace's emergency procedure.
- During migration, 30 available media files were copied to S3. Ten older audio records already lacked their source files. Their reports and transcripts remain, but those original recordings cannot be recreated from text.

For a local Docker setup, see [deployment](docs/deployment.md). For the running AWS setup, use the [release and recovery guide](docs/aws-deployment.md). Review the configured credentials and rotate any that have been exposed before sharing access broadly.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/pages/workspace/` | Owner, supervisor and worker screens |
| `src/components/workspace/` | Shared forms, voice controls and conversation UI |
| `src/styles.css` | Theme, layout and shared control styles |
| `backend/app/api/` | Authentication and application endpoints |
| `backend/app/services/` | Reports, comparisons, tasks, handovers and evidence rules |
| `backend/app/models/` and `backend/app/mongo.py` | Schema and MongoDB persistence |
| `backend/app/worker.py` | Background speech, email and scheduled jobs |
| `deploy/aws/` | Infrastructure, releases, HTTPS and backup scripts |
| `docs/` | Architecture, integration details, coverage and validation |

[Architecture](docs/architecture.md) · [Integrations](docs/integrations.md) · [Feature coverage](docs/coverage.md)

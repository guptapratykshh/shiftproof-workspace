# Architecture and implementation decisions

## Application boundaries

React/TypeScript renders the public pages and role workspaces. React Query owns server state; Zustand holds the current session in memory. FastAPI validates requests using Pydantic, enforces authorization centrally and delegates workflows to services. SQLAlchemy models and Alembic migrations support PostgreSQL and SQLite for development. The API and background worker share the database and private evidence store. An nginx frontend proxies `/api/v1`; the optional production Caddy service terminates HTTPS.

The API is the authority for permissions, lifecycle transitions, verification, report receipts and metrics. There are no hardcoded dashboard populations or simulated successful submissions. Frontend controls are convenience, not authorization. The API's OpenAPI reference is available at `/docs` on the API origin during local development.

## Identity and access

A verified registration creates the organization and first administrator. Invitations and recovery links are expiring, single-use tokens stored as hashes. Workers use an organization code, employee ID and their own six-digit PIN. Passwords/PINs use Argon2. Session tokens are hashed at rest and sent using HttpOnly cookies. Mutations require a session-bound CSRF token. Account/IP rate limits, idle/absolute expiry, session revocation, last-active-admin protection and individual audit attribution are enforced on the server.

Supervisor permissions are independent per department. Administrator visibility does not imply permission to conduct operational decisions; a reasoned, expiring takeover enables those actions. Administrative original-report/recording access requires the configured privacy permission or takeover plus a recorded purpose. Worker data is scoped to their departments, assigned tasks, own reports and relevant handovers. Private file downloads recheck authorization and retention at access time.

## Operational integrity

Task acceptance, start, completion, supervisor verification and closure are separate events. Critical tasks require approval; rejected completion returns the task to active work. Shared work is one task with team ownership, not duplicated per-worker completion. Assignment validation checks active membership, qualifications/expiry, availability and shift eligibility. Routine template allocation uses eligible workload/fairness ordering and never auto-allocates critical work.

Reports retain separate source transcript, extraction and human-confirmed immutable versions. Corrections create a version rather than incrementing the report count. A report review/verification cannot resolve conditions or complete linked work. Conflicts retain both sources and a supervisor's decision. Cross-department referrals expose the purpose-limited referral without granting access to unrelated original evidence. Concurrent assignment claims prevent duplicate follow-up tasks.

A report's UUID is unique per organization and original author. Stable request hashes reject changed-content reuse of the same key. A user-row lock serializes simultaneous retries; the final receipt always comes from the API. Immediate alerts have their own idempotency key and link to the later report so an early safety notification does not duplicate on submission.

Published handover snapshots, report versions, reviews, task verification/history, alert history and audit records are append-only. ORM guards and PostgreSQL/SQLite database triggers reject edits/deletes. Current mutable task/report rows use optimistic version checks for conflicting actions. The handover version and recipient/item are recorded with each acknowledgement. Overall receipt never substitutes for individual critical-item receipt.

## Offline and shared devices

IndexedDB stores AES-GCM encrypted envelopes partitioned by organization/user, with a random server-provided key held only in memory during the authenticated session. Media is inside the encrypted payload. Locking/signing out clears the in-memory key and server cache. Account changes invalidate other tabs. Queued API requests carry the original account ID, which the server validates against the current cookie session. Cross-tab Web Locks serialize queue processing.

States remain distinct: Draft, Saved Locally, Pending Sync, Syncing, Submitted and Sync Failed. Upload IDs are saved for safe retry. A confirmed receipt clears the local report text/media while preserving its reference. The service worker precaches versioned static bundles; it never caches authenticated API responses, credentials or account data. A fresh offline reload cannot unlock prior-worker drafts.

## Jobs and integrations

Durable database jobs use unique deduplication keys, conditional claims, leases, bounded retries/backoff and crash recovery. The minute scheduler processes escalation, deadline/receipt reminders, recurrence, provisional handovers and retention. Provider failures cannot overwrite confirmed reports. Transcription/extraction failures retain source material and expose a manual text path. AI output remains a suggestion: no autonomous verification, closure, conflict adjudication or safety suppression.

Expired raw transcripts and evidence are unavailable immediately on read even if the scheduler is delayed; the scheduler removes raw source data/files. Human-confirmed reports and decision history have separate archival semantics and are not silently erased by raw-audio retention settings. Email jobs clear raw delivery links after successful delivery; development `.eml` files remain private local artifacts and should be removed when no longer needed.

## Defaults chosen by this implementation

These numerical defaults are engineering choices, not numbers asserted by the PDF.

| Setting | Default |
| --- | --- |
| Verification / password reset | 24 hours |
| Supervisor / worker activation invitation | 72 hours unless issued as a reset |
| Absolute session expiry | Workers 8 hours; other roles 12 hours |
| Idle expiry without an explicit organization policy | Workers 60 minutes; other roles 120 minutes |
| Login rate threshold | 8 account failures / 60 source-IP failures in 15 minutes |
| Primary acknowledgement / backup escalation wait | 10 minutes each |
| Deadline / handover receipt reminder | 30 / 15 minutes |
| Provisional handover grace | 15 minutes, configurable per shift |
| Raw recording retention | 30 days |
| Raw transcript / photo or document retention | 365 days |
| Recording UI limit | 29 seconds per clip |
| Maximum uploaded file | 25 MiB |
| Background processing | 3 attempts; 3-minute lease; bounded exponential retry |

Department health is deterministic: open critical alerts make it critical; blocked/overdue work makes it need attention; otherwise healthy. Historical charts display actual data only. Each analytics response includes cohort/denominator definitions; filtering a period is different from the all-current-items attention queue.

## Deliberate implementation choices

The screenshot illustration is an editable SVG recreation because the original asset was unavailable. Shared native/React UI primitives are used rather than adding a second component framework. Repository modules separate pages by operational area; the service layer owns business decisions. SSE supplies updates and polling provides a reconnect fallback. SQLite is for local convenience and tests; production settings reject it. Provider adapter contracts follow official documentation, but credentialed integration validation remains a separate step.

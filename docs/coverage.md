# ShiftProof feature coverage

This maps the PDF and pasted master prompt to the local implementation. The screenshots govern the public composition and shared theme; the PDF/master prompt supply operational behavior. The user's latest instruction keeps the full app local and deployment-ready. Earlier static-only scope statements in the old README have been removed.

**Implemented** means connected UI/API/persistence exists. **Automated** identifies executable checks, not a claim that every subclause, browser, load level or live provider has received acceptance sign-off. The two detailed requirements inventories retain their source checkboxes so unreviewed individual clauses are not silently marked complete.

| Requirement area | Implementation | Verification / practical boundary |
| --- | --- | --- |
| Landing and sign-in references | `Landing.tsx`, `SignIn.tsx`, `FactoryScene.tsx`, global tokens | Public browser tests and desktop/mobile visual review; illustration is an editable recreation |
| Signup and eight organization types | Shared forms, registration schema, verified organization creation | Required fields, validation, duplicate handling, email verification before organization creation |
| Role login, recovery, invitations | `auth.py`, `authentication.py`, activation/recovery screens | Real API tests for activation, hashing, CSRF, tenant isolation, last admin and inactive-account recovery |
| Nine-step organization setup | Onboarding UI, activation gates, editable organization profile/logo/timezone | First five required, active supervisor required, optional privacy customization never removes defaults |
| Departments and teams | CRUD with soft state; overview/detail pages and membership links | Scope checks, case-insensitive duplicate detection, inactive assignment rejection; historical records retained |
| Supervisor management | Invite/activate, per-department permissions, primary/backup mapping, details/history | Department permissions and administrator-only controls enforced server-side |
| Shift structure and scheduling | Overnight definitions, overlap warnings, assignments, timeline, coverage matrix and weekly calendar | Overnight next-shift/date routing tested; individual schedule changes are explicit, not an inferred rotation engine |
| Privacy, policies and takeover | Privacy/retention, reminders, security settings, escalation/responsibility rules, expiring takeover | Administrative evidence gate/purpose and operational authority are separate; sensitive access audited |
| Worker onboarding | Email-free identity, own-PIN activation, supervisor-assisted reset | No plaintext PIN retrieval; activation links and identity verification have API tests |
| Bulk workforce import | CSV/XLSX template, validation, preview, valid-row confirmation | Invalid rows not imported; duplicate preview/confirmation is tested |
| Worker memberships/qualifications | Primary/additional departments, teams, skills, expiry, current workload | Eligibility, qualification removal/expiry and absence checks tested |
| Absences and reassignment | Availability history/correction; individual/bulk task reassignment | Existing critical work stays open and visible; changes are attributed and audited |
| Task lifecycle | Accept, start, block/resume, complete, verify/reject and close | Worker-to-supervisor browser flow; ordinary/critical transitions and approval boundaries tested |
| Shared team work | One task, current team assignment and optional lead, shared comments/history | Shared completion stays one record; worker internal-note restrictions tested |
| Task planning | List/board/calendar, filters, dependencies, private attachments, templates/recurrence and routine allocation | Dependency, concurrent reassignment, task evidence and routine-allocation constraints tested; board/calendar show up to 200 matching records with notice |
| Worker home/reporting | Report action prominent; scoped tasks prioritized by criticality/priority/deadline; current shift/context | Real API worker flow, responsive review and English/Hindi controls |
| Voice and text reports | Consent, recording duration/cancel, original transcript, structured extraction, editable review/confirmation | Text and provider-failure paths tested; live Gnani/Gemini success needs credentials |
| Task association | Actual visible-task suggestions and explicit confirmation; supervisor existing-task linking | Another worker's private task cannot appear in suggestions; linking is audited and does not imply closure |
| Report history and review | Immutable corrections, source/AI/confirmed separation; reviewed/verified/clarify/escalate/resolve actions | Version history and resolution gates tested; review does not resolve unresolved work |
| Conflict clarification | Both originals retained, neutral questions, response types and authorized decision | Conflicting reports and corrections tested; bounded unanswered questions prevent repeated prompting |
| Immediate safety | Immediate alert before routine report submission; later report links same alert | Idempotent immediate-alert browser/API tests; critical safety counted even under general report category |
| Alert handling and escalation | Primary/backup/administrator routing, acknowledgement/investigation/corrective action/verification/resolution | Escalation/defaults and distinct acknowledgement/resolution tested; application does not replace emergency procedures |
| Cross-department follow-up | Origin preserved, limited referral, receiving-department task, source linkage | Privacy boundaries and simultaneous assignment deduplication tested |
| Handovers | Draft compilation/notes, explicit publication, version history/comparison, provisional generation | Immutable publication, overdue provisional generation, overnight recipients and updated versions tested |
| Handover receipt | Overall version receipt plus separate required critical-item acknowledgements | API and browser checks verify both levels; reminders remain pending independently |
| Notifications | Relevant in-app inbox, categories, read/unread, deep links, SSE/reconnect; opt-in desktop alerts; configured email escalation | Read does not acknowledge tasks/handovers; notifications are account/department scoped. No SMS/mobile push integration is claimed |
| Offline reporting | Encrypted IndexedDB, separate states, UUID/request hash, retry, cross-tab locking, explicit account header | Browser tests cover encrypted local persistence, reconnect receipt and account switching; concurrent API retries create one report |
| Shared-device sessions | Memory-only session/key, explicit logout, local lock, idle/absolute expiry and revoked sessions | Passive polling cannot extend an idle session; a full offline reload cannot unlock a workspace |
| Real analytics | Seven families: tasks, safety, quality, reports, workforce, handovers and cross-department comparison | Real aggregation tests, date/scope filters, charts and CSV export; responses document cohorts/denominators |
| Audit and immutable history | Individual attribution, redacted sensitive access, immutable version/history tables | MongoDB application persistence guards; native transaction/immutability tests. Legacy PostgreSQL/SQLite trigger tests remain separate. |
| Background processing | Database queue, deduplication, leases/recovery, retry/backoff, recurring scheduler | Lease/failure tests; operational monitoring and queue screens available |
| Evidence and retention | Private disk/S3 adapter, validation, photo metadata removal, consent, scoped downloads and retention | Private-file/read-time-retention tests; live S3 and PDF scanner configuration still required |
| Local/deployment tooling | Native full-stack launcher, lockfiles, Docker/external MongoDB/nginx/Caddy config, migration and backup/restore scripts | Native app and production bundle checked; compose parsed. Docker daemon/build/TLS and external services not verified here |

## Verification record

The executable sources are `tests/pages.spec.ts`, `integration/workspace.spec.ts`, `backend/tests/test_workflows.py`, `backend/tests/test_integrity.py`, `backend/tests/test_migrations.py`, `backend/tests/test_mongo.py` and the legacy `backend/tests/verify_postgres_restore.py`. The workspace suite uses a real isolated API/database; API tests run on MongoDB Atlas and isolated SQLite; prior PostgreSQL results are retained separately. `SHIFTPROOF_BUILD_TEST=1 npm run test:workspace` serves a production bundle and also checks the offline static shell.

Public responsive checks cover 320, 390, 768, 900, 1169 and 1600px in both languages/themes. Operational responsive checks cover the same six widths across 15 administrator routes, 17 supervisor routes and 13 worker routes, including record details, list/board/calendar views and a 320px task form. Mobile navigation keyboard dismissal and Hindi/light review are also checked. Visual capture files live in `artifacts/review/` after the final run. Browser tests are not exhaustive assistive-technology or device-farm certification.

The PostgreSQL recovery drill uses actual migrations, database history constraints, `pg_dump`/`pg_restore` and a paired evidence checksum. It does not prove a future host's automated backup schedule. The original SQL drill is retained for legacy recovery. Current MongoDB BSON backup/restore instructions are in `docs/deployment.md`.

## Items requiring environment-specific acceptance

- Configure and exercise entitled Gnani Prisma/Timbre and Gemini models with consented samples. Adapters and safe unavailable/error behavior are implemented; live speech/extraction quality is not certified.
- Configure and verify production SMTP, optional private S3 and an updated PDF scanner. Credentials and infrastructure were not supplied.
- Build/run the Docker stack on a host with a working daemon; verify HTTPS, cookies, real email, operational worker scheduling and restoration there before production use.
- Review representative factory data, roles, shift/timezone rules, Hindi terminology, recording-retention policy and critical-task acceptance with the organization. The product defaults are documented engineering choices.
- Large-scale load, multi-instance stress, screen-reader/device-farm audits and formal security review remain outside the local automated checks. Existing pages are functional; passing tests are not a production certification.

No provider success, remote deployment, sample analytics or production account is fabricated to mark these items complete.

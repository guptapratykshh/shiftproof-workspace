# Local validation: 1 November 2026

## MongoDB primary database: 5 November 2026

Work was completed in the original `shiftproof` checkout; the temporary migration worktree and branch were removed. The Mac Wi-Fi DNS was changed to Cloudflare/Google with the user's explicit approval after the router failed Atlas DNS resolution.

- Migrated and SHA-256 verified **2,172 records across 50 mapped collections** into the separate Atlas **`shiftproof`** database. The supplied `food-rescue` database was not used.
- Kept a consistent SQLite/evidence backup under ignored `backend/data/backups/`. The old SQLite file stayed unchanged after the live app started writing to MongoDB.
- Existing Atlas workflow/integrity/email cases: **41 passed** across the complete run and the targeted rerun after fixing JSON lookup and simultaneous report retries. The additional legacy SQL migration test passed separately in that run.
- New native MongoDB tests: **4 passed**, covering rollback, timestamp precision, optional-null uniqueness, references, immutable history, competing writes/job claims, resumable verified import, refusal to overwrite, and actual BSON backup/restore with indexes and checksums.
- SQL regression suite: **42 passed, 4 Mongo-only tests skipped**. Production frontend build passed. Compose configuration and backup/restore shell syntax passed; Docker container execution remains unverified.
- Local and public API health both reported `database_type: mongodb`, connected, with zero failed background jobs. The scheduler continued completing jobs after restart.
- Public browser checks passed for landing/signup, all three roles, saved preferences, automatic notifications and untrusted-origin rejection, with no browser errors. Temporary verification accounts were removed afterward.

Browser responsive coverage passed at 320, 390, 768, 900, 1169, 1470, 1600, 1920 and 2560 CSS pixels across English/dark and Hindi/light workspace screens. The complete workspace run passed five cases; two initially failing browser checks passed on focused rerun after waiting for dialog save completion and finishing the database switch. Combined result: **7 passed, 1 production-only case skipped**. The task and handover flows were verified through the real Atlas-backed API. The production-only offline-shell case was not repeated in this database pass.

The previous quick tunnel expired and was replaced. Its current address is stored in ignored `.sites-runtime/public-tunnel.json`; public access still depends on this Mac and its local services. MongoDB credentials and SMTP settings remain private and were excluded from commits. Evidence remains in local/private object storage rather than in MongoDB.

Earlier sections below are historical validation records, including the former SQL deployment.


## Theme interaction update: 2 November 2026

The shared sun/moon button now switches directly between light and dark on every public and workspace screen. The appearance menu and the separate Settings appearance selector were removed. Choices persist across routes and reloads; an older saved System preference is converted once to its currently resolved light/dark appearance. Keyboard activation keeps focus on the button, with action labels in English and Hindi.

The public browser suite passed all 17 cases. Two focused production workspace cases passed, covering worker/supervisor switching and the administrator's Hindi theme button and Settings screen. The production build and whitespace check passed; current review captures were refreshed. The remaining results below describe the earlier validation passes.

| Check | Result |
| --- | --- |
| TypeScript and Vite production build | Passed; production API proxy base and static-only offline manifest included |
| Backend workflows / integrity / migrations / mail on SQLite | 42 passed, including 7 mail configuration and delivery tests |
| Backend suite against dedicated PostgreSQL 17 schemas | 35 passed |
| Actual PostgreSQL migration upgrade/downgrade/upgrade and restore drill | Passed; immutable-history UPDATE/DELETE rejected; database and paired evidence checksum restored |
| Public browser suite | 17 passed after spacing refinement |
| Production workspace browser cases | All 6 cases passed together against the updated production build |
| Mail confirmation browser cases | 2 passed against a production build; local/queued SMTP states, signup/recovery, English/Hindi at 320px |
| Live local Gmail SMTP | Verified STARTTLS authentication and a real verification message; worker reported `smtp_accepted` on the first attempt |
| Final capture and mobile keyboard regression run | 3 passed; Escape closes navigation and restores focus |
| Responsive public pages | 12 routes × 9 widths × 2 themes × 2 languages; shared gutters and illustration height checked |
| Responsive operational pages | 21 administrator, 23 supervisor and 13 worker routes at 9 widths in English/dark and Hindi/light; content width, padding and clipped controls checked; board/calendar and 320px task form included |
| Dependency audit | `npm audit --omit=dev`: 0 vulnerabilities reported |
| Development and production compose parsing | Passed, using non-secret placeholder values for production-required variables |
| Whitespace / patch checks | `git diff --check` passed |
| Native full-stack startup | Frontend and proxied API HTTP 200; database connected; background worker processing; no failed jobs at final check |
| Review artifacts | 19 current desktop/mobile captures in `artifacts/review/`, with an HTML gallery |

The six workspace cases exercise critical-task approval, encrypted offline synchronization/account isolation, administrative responsive pages, immediate-alert deduplication and two-level handover receipts, a static-only production offline shell, and worker/supervisor detail-page responsiveness. The offline shell test found and verified the fix for static-asset cache matching with `Vary: Origin`. API responses are never placed in the service-worker cache.

The final capture run disables CSS animation during capture so resizing does not photograph a sidebar or theme transition halfway through. Public landing/sign-in composition and signup styling were manually reviewed, along with desktop dashboards and mobile report/analytics layouts. The task-form capture uses a 320px viewport. Operational captures show isolated synthetic QA records, not user organization data.

## Spacing refinement

The shared frame uses 16px side gutters through 600px, 24px through 1000px, and `clamp(32px, 2.5vw, 48px)` on desktop. The landing header and all content sections now align at both edges. Sign-in cards and workspaces use the available width, while signup and individual authentication forms retain 960px and 560px maximum widths. The editable SVG keeps its proportions and a 320px desktop height cap.

The target CSS viewport widths were 320, 390, 768, 900, 1169, 1470, 1600, 1920 and 2560px. The landing reference capture uses 1470 × 801 CSS pixels at 2× pixel density, without browser chrome; both full-page and viewport images are available. At this desktop width, each outer gutter is 36.75px.

The expanded control checks caught crowded attention badges and notification actions on narrow screens. Mobile attention badges now occupy a separate row, and notification actions sit below their message. Both corrected layouts were checked and captured at 320px. Workspace layout sweeps load each route and then resize it across all nine widths; this avoids repeated full application boots while checking every requested size. The final production workspace run passed all six cases together in 2.9 minutes.

This pass reran the frontend build and both browser suites. The backend, PostgreSQL, dependency and deployment checks above are retained results from the preceding full-app validation; no backend, API or deployment configuration changed in this spacing pass.

## Email delivery follow-up

Gmail SMTP was configured in the ignored, owner-readable `backend/.env`, and the native API/worker were restarted. A fresh link was generated for the matching unverified registration and sent through the durable worker. Gmail accepted the message; inbox placement and the user's click are not claimed. No SMTP credential or verification token is included in tracked files or this report.

Signup and recovery now distinguish local capture from queued SMTP delivery. STARTTLS validates certificates and hostnames, and authenticated SMTP rejects a missing password at configuration time. The complete SQLite backend suite passed 42 tests; the two focused browser cases and production build passed. Automated mail tests use fake transports and isolated fixtures, not live recipients. The preceding PostgreSQL and general browser results remain retained checks, rather than newly repeated claims.

## Unverified external/runtime paths

- No live Gnani Prisma/Timbre or Gemini calls were made without credentials. Failure/unavailable and structured-output grounding behavior has automated coverage.
- SMTP from the eventual production host, optional private S3 and a configured PDF malware scanner need environment-specific success-path checks. Native Gmail SMTP has been verified; the generic development template still defaults to local capture.
- Docker CLI/Compose are installed, but the Docker daemon socket was unavailable. Container builds, container startup and Caddy TLS issuance were not run. Compose parsing alone does not certify them.
- Load, multi-instance stress, exhaustive assistive-technology/device testing and independent security review are not claimed.

The build emitted non-failing third-party Zod annotation warnings. Backend tests emitted a Starlette/httpx deprecation warning. Neither prevented the checks above; locked versions are retained.

The QA PostgreSQL server and temporary preview were stopped after verification. The native development launcher remains available at http://localhost:5173, using its own unseeded local database. Start it again with `npm run dev:full` if the current terminal session ends. No new remote deployment was made.

# Local validation — 1 November 2026

## Theme interaction update — 2 November 2026

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

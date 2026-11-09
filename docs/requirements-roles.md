# ShiftProof role requirements audit

Source: **SHIFTPROOF_ DOCUMENTATION.pdf**, Section 2 (Organization Admin, v1.1), Section 3 (Supervisor, v1.0, labeled Draft: Under Review), and Section 4 (Worker, v1.0). Extracted from the complete text of those sections, corresponding to lines 421–4033 in the local PDF text extraction. The current user request includes all documented features.

Every checkbox is initially unchecked. This document is a requirements inventory, **not a claim of implemented or verified functionality**. Mark an item complete only after both its applicable UI and backend behavior are implemented and verified. Section references use `S2 §3.2` for Section 2, subsection 3.2.

## Organization administration

### Navigation, identity, and authentication: S2 §§1–2

- [ ] Provide admin navigation: Overview, Departments & Teams, Workforce, Shifts & Scheduling, Supervisor Management, Policies & Permissions, Alerts & Escalation, Analytics & Reports, Audit History, Settings. Include organization identity/logo, current administrator, notifications, theme selection, and logout; keep organization setup accessible after onboarding.
- [ ] Registration requires full name, official organization email, password, confirmation, organization name, and organization type; contact number is optional.
- [ ] Include all eight organization types: Manufacturing, Equipment Maintenance, Warehousing, Quality Assurance, Food Processing, Construction, Healthcare, Facility Management. Permit future expansion without restructuring onboarding.
- [ ] Validate email format, security policy, password confirmation, and required fields; prevent duplicate organization records. Verify the email before creating the organization account and entering onboarding. Public organization registration is available only to administrators, not supervisors or workers.
- [ ] Admin login uses official email and password, with password recovery and organization-registration links. Resolve the organization and permissions, then route to incomplete onboarding or the organization dashboard.
- [ ] Allow existing administrators to invite additional individual administrators with organization-level administrative permissions by default. Preserve individual attribution; no shared administrator credentials.
- [ ] Audit administrator access changes and preserve historical attribution after deactivation. Prevent deactivation or removal of the last active administrator.

### Resumable nine-step onboarding: S2 §3

- [ ] Present nine guided steps with saved progress, Save & Continue, and Save & Exit. Require the first five before activating operational functionality; optional customization remains available afterward. Skipping policy customization must not disable privacy or recording safeguards.
- [ ] **Step 1, organization profile (S2 §3.2):** require name, type, valid contact email, and explicitly configured timezone; allow logo, address, and contact number. Accept common logo image formats and make organization details editable later in Settings.
- [ ] **Step 2, departments (S2 §3.3):** list/add/edit/deactivate departments with required name and optional description. Prevent or explicitly handle organization-local duplicates. Require at least one active department. Preserve historical departments; inactive departments cannot receive new assignments.
- [ ] **Step 3, teams/production lines (S2 §3.4):** create beneath an active department with required department-unique name and optional description; list/add/edit/deactivate. Preserve historical memberships. Inactive teams cannot receive assignments unless reactivated. Require at least one active team/production line globally.
- [ ] **Step 4, shift definitions (S2 §3.5):** require name, start time, end time, and working days; allow rotation rule and description. List/create/edit/deactivate shifts and show timing visualization. Require at least one active shift.
- [ ] Validate shift times; support overnight shifts, overlap warnings, and next-shift calculation across midnight. Preserve historical shift definitions when changed/deactivated. Administrators control organization definitions; supervisors only manage daily assignments within them.
- [ ] **Step 5, primary/backup supervisors (S2 §3.6):** require full name, official email, department assignments, permission level, and primary/backup designation; contact number optional. An administrator creates/invites the account; supervisor receives activation link, chooses password, and becomes active.
- [ ] Permit multi-department supervisor assignments with independent permissions, including different primary/backup coverage by department and shift. Require at least one **active** designated supervisor responsible for operational alerts; a pending invitation alone does not satisfy activation.
- [ ] **Step 6, optional responsibility mapping (S2 §3.7):** map supervisors and backups to departments, teams, production lines, machines, operational areas, and responsibility categories. Use mappings for report, alert, and handover routing. Unmapped issues fall back to the department primary supervisor.
- [ ] **Step 7, optional escalation customization (S2 §3.8):** configure primary/backup recipients, acknowledgement response window, escalation recipient, severity/unacknowledged conditions, and supported notification channels. Escalate according to severity or expired response window.
- [ ] Preserve safe escalation defaults when customization is skipped: primary routing, configured backup notification, missing-backup warning, and immediate-safety emergency escalation without waiting for AI or a timeout. Make clear that the application complements organization emergency procedures.
- [ ] **Step 8, optional privacy/recording customization (S2 §3.9):** configure recording disclosure/consent, recording/transcript retention, original recording access, role-based evidence access, visibility/sharing, and organizational privacy requirements. Mandatory safeguards always apply; enforce retention and permission rules and audit policy changes.
- [ ] **Step 9, optional final review (S2 §3.10):** summarize profile, departments, teams/lines, shifts, supervisors, mapping, escalation, and privacy. Show Completed/Pending/Skipped/Requires Attention, edit-section links, activation, and save/exit.
- [ ] Enforce activation gates independently of the optional review UI: first five steps complete, at least one active department/team/shift/designated supervisor, and a responsible critical-alert recipient. Optional configurations may remain incomplete after activation.

### Organization dashboard: S2 §4

- [ ] Header shows organization identity/logo, current date, date-range selector, notifications, profile, and theme controls.
- [ ] Overview indicators show active departments, active workers, active supervisors, tasks in progress, open critical issues, and pending escalations; each includes icon and drill-down. Show equivalent-period comparisons and sparklines only with meaningful historical data; never invent percentage changes.
- [ ] Compare departments by completed/pending/overdue tasks and open critical issues. Define deterministic Healthy/Needs Attention/Critical criteria; do not use arbitrary AI labels. Department selections open detailed views.
- [ ] Show task distribution including Assigned, Accepted, In Progress, Blocked, Completed, Awaiting Verification, and Closed; task completion trends; overdue tasks by department.
- [ ] Show critical issues that are open, new, awaiting acknowledgement, awaiting corrective action, and escalated; severity distribution and trends. Preserve a prominent actionable alert list alongside charts.
- [ ] Show workforce distribution by department and shift; highlight missing primary/backup supervisor coverage by department and shift.
- [ ] Show handovers published over time, overall acknowledgement rate, individual critical-item acknowledgement rate, pending acknowledgements, and publication delays.
- [ ] Organization alerts focus on escalations/configuration problems rather than routine reports. Each shows severity, department, issue, responsible supervisor, age, status, and available action.
- [ ] Configuration progress exposes missing backups, unmapped responsibilities, default escalation settings still in use, and pending privacy customization with clear actions.
- [ ] Recent activity emphasizes significant organization changes, supervisor additions, structure changes, critical escalations, and policies. Routine operational events remain within department views.
- [ ] All charts use actual records, clear titles/labels, appropriate legends/tooltips/date filters, underlying-record navigation, semantic colors plus non-color cues, and meaningful empty states. Avoid unnecessary duplicate charts and misleading representations of incomplete data.

### Departments, teams, and workforce: S2 §§5–6

- [ ] Department list shows name, team/worker counts, assigned supervisors, open critical issues, active state; create/view/edit/deactivate actions and department workforce/issue comparisons.
- [ ] Department detail includes overview, teams/lines, supervisors, workforce, operational summary, and activity history; task status/worker/severity/completion charts; team and supervisor detail links. Routine assignment/issue handling remains primarily in the supervisor experience.
- [ ] Team detail shows name, parent department, description, workers, responsible supervisor, and active state; edit, membership management, and deactivate actions.
- [ ] Organization-wide workforce directory shows Employee ID/name, primary/additional departments, team memberships, shift, and account state; filters by department/team/shift/account state; view/edit/deactivate/reactivate. Routine worker onboarding is primarily supervisor-driven.
- [ ] Workforce visualizations cover department/shift distribution, active versus inactive workers, and department comparison. Worker detail includes identity, memberships, shift assignments, account state, and relevant assignment history.
- [ ] Never expose worker PINs or other sensitive authentication values to administrators or supervisors.
- [ ] Administrators do **not** receive unrestricted original recording or transcript access by default. Enforce explicit privacy policy/permissions and legitimate organizational purpose; log recording/transcript access and preserve historical reports.

### Supervisors, scheduling, and permissions: S2 §§7–9

- [ ] Supervisor directory shows name, ID, email, assigned departments, independent permission levels, primary/backup designation, and account state; invite/edit/change permissions/change responsibilities/deactivate; distribution and coverage visualizations.
- [ ] Supervisor detail includes profile, department assignments, permissions, responsibility mapping, shift coverage, and activity history.
- [ ] Enforce department-specific access such as full operational, view-and-monitor, and no access. Managing several departments never implies organization-wide access; only administrators control global permissions.
- [ ] Temporary supervisor takeover lets an administrator select a department and responsibilities, explicitly activate temporary operational permissions, see a takeover indicator, and end it manually. Attribute actions to the actual administrator and audit the takeover/actions/end; expire or revoke temporary access without changing permanent assignments.
- [ ] Scheduling overview shows workers/supervisors by shift, department coverage, missing supervisor coverage, and worker availability, using shift distributions, coverage matrix, and weekly calendar.
- [ ] Supervisors may assign workers and permitted replacements/swaps within organization shift definitions. Record changes; use shift assignments for handover routing and responsibility.
- [ ] Central policy management covers role permissions, department access, data visibility, recording safeguards, evidence access, retention, and account security. Supervisors cannot change global policy/self-grant permissions; workers cannot change administrative settings; enforce all rules server-side.
- [ ] Administrator invitation/deactivation/access management remains individually traceable and always retains at least one active administrator.

### Alerts, analytics, audit, and settings: S2 §§10–14

- [ ] Alert administration supports severity configuration, department responsible supervisors, primary/backup recipients, escalation rules/windows, and history. Visualize severity/department distribution, escalation trend, average acknowledgement time, and pending versus resolved issues.
- [ ] Responsible supervisor receives initial alerts; severity/time policies govern escalation; immediate safety invokes emergency escalation. Track acknowledgement separately from resolution and record every escalation.
- [ ] Analytics categories include task completion, overdue tasks, critical issues, issue resolution time, department performance, handover completion/acknowledgement, workforce distribution, reporting trends, and supervisor coverage.
- [ ] Analytics filters include date range, department, team, shift, task category, and issue severity. Provide appropriate donut/line/bar/stacked-bar/progress/heatmap/coverage-matrix views, underlying-record drill-down, and supported exports. Enforce privacy and defined calculations/cohorts; preserve history and avoid insufficient-data claims.
- [ ] Use the master prompt's detailed metric definitions where Section 2 defers KPI calculations rather than inventing conflicting formulas.
- [ ] Audit organization/configuration, department/team/shift changes, supervisor/admin invitations/account changes, permissions, workers, escalation/privacy settings, temporary takeovers, and administrative actions.
- [ ] Audit record fields: event ID, actor, actor role, action, affected entity, timestamp, previous/new value where applicable. Ordinary workflows cannot silently modify/delete audit records.
- [ ] Settings include organization identity/logo/type/contact/timezone/preferences; own profile/password/active sessions/notification preferences; administrator invitations/access/deactivation; persistent light/dark/system theme.
- [ ] Every admin screen supports loading, useful empty/action states, errors/retry, permission errors, network failures preserving unsaved input, confirmation for consequential changes, and informative insufficient-analytics-data states.

### Admin acceptance gate: S2 §15

- [ ] Verify registration/email verification, all mandatory onboarding and save/resume, eight organization types, multiple-admin management, departments/teams without historical deletion, overnight/multiple shifts, supervisor invitations/multi-department permissions, workforce visibility, escalation, temporary takeover, privacy-controlled evidence, visual analytics/drill-down, and audit history end to end.
- [ ] Verify historical preservation after structure changes, independent backend authorization, actual-data charts that retain actionable alerts, light/dark themes, and desktop/tablet/mobile support.

## Supervisor experience

### Navigation, authentication, and first use: S3 §§1–3

- [ ] Supervisor navigation includes Overview, Needs Attention, Tasks, Reports & Issues, Handovers, Team Management, Notifications, Settings; organization identity, current department/selector, shift, notifications, profile, theme, logout.
- [ ] Supervisor accounts are administrator-invited only. Login requires email, Organization ID, password; include recovery and account activation. Load only assigned departments and their permission levels. Supervisor ID as an alternative identifier is conditional on architecture support.
- [ ] Provide a skippable/resumable five-step first-use checklist: review departments/permissions/teams/primary-backup; review teams/workers/availability/memberships; confirm assigned shifts/responsibilities/mappings; learn incoming handovers/critical acknowledgement/transfers/history; enter dashboard with feature orientation.
- [ ] Save supervisor onboarding progress, avoid repeating completed steps, allow experienced users to skip directly to dashboard, and never expose organization-wide configuration editing through onboarding.

### Dashboard and attention queue: S3 §§4–5

- [ ] Provide individual-department and combined authorized-department views, enforcing independent permissions even in combined view. Header includes greeting/name/date/time/current shift/department selector/notifications/profile.
- [ ] Attention summary links to filtered critical alerts, blocked/overdue tasks, pending approvals, unresolved conflicts, and pending critical acknowledgements.
- [ ] Use actual-data task-status/progress/severity/workload/overdue visualizations and relevant recent reports/tasks/issues/corrective actions/supervisor actions; routine activity must not dominate.
- [ ] Upcoming handover shows current status, shift-end countdown, unresolved issue count, pending transfers, draft status, and review action.
- [ ] Attention queue includes critical alerts, blocked/overdue tasks, completed tasks requiring approval, conflicts, uncertain critical reports, pending critical acknowledgements, and missing required evidence.
- [ ] Prioritize immediate safety, critical incidents, critical-task approval, high-impact conflicts, blocked tasks, overdue tasks, then other actions. Routine updates must not bury critical issues.
- [ ] Each attention item displays title, severity/flag, department/team, responsible worker, timestamp, status, reason for attention, primary action, and detail navigation.

### Tasks: S3 §6 and S4 §4

- [ ] Task list shows title/ID, department/team, assignee worker/team, priority, deadline, status, verification requirement. Filters: department/team/worker/status/priority/deadline/category. Provide list and board; PDF makes calendar architecture-dependent, but master prompt explicitly requires calendar.
- [ ] Create-task required fields: title, description, department, individual/team type, assigned worker/team, criticality, verification-required. Optional: team, deadline, priority flag, supporting attachments, instructions. Keep optional priority flag distinct from required criticality.
- [ ] Flags: Critical/Urgent/Important/Normal; no flag mandatory. Critical requires supervisor approval before closure; urgent is prominent; important visually emphasized. Workers cannot change supervisor flags; changes recorded; AI never silently changes them and AI risks are visually distinguishable.
- [ ] Individual tasks have one responsible worker. Team tasks remain a single shared task rather than per-worker duplicates; optional lead and traceable individual contributions where supported.
- [ ] Routine predefined automatic allocation considers department eligibility, skills/qualifications, workload, shift availability, and fairness. New/specialized/high-priority proposals require supervisor approval. Supervisors may modify assignments; never assign unqualified workers merely for load balancing.
- [ ] Preserve lifecycle Assigned → Accepted → In Progress → Completed → Verified when required → Closed, plus Blocked. Acceptance, completion, verification, and closure remain distinct.
- [ ] Ordinary worker-completed tasks may close without mandatory verification. Verification-required and critical tasks require authorized supervisor approval before closure; workers cannot bypass it.
- [ ] Completion rejection requires a reason, restores the appropriate state, notifies worker, and records history.
- [ ] Reassign for absence/unavailability/workload/qualifications/shift changes; preserve original assignments/progress/evidence, record reason, notify new assignee, update workload, enforce qualifications.
- [ ] Task detail shows information/instructions, assignment, flag/deadline/status, progress, worker reports, attachments, comments/updates, verification history, reassignment history; actions follow permissions.
- [ ] Worker task categories: To Do, In Progress, Blocked, Completed. Keep tasks awaiting review visible as Awaiting Approval. Cards include title/short description/priority/deadline/department-team/status.
- [ ] Worker task detail includes supporting evidence, supervisor instructions, updates, and worker-visible comments; never expose internal supervisor notes.
- [ ] Worker actions by ownership/state: accept/start/update progress/report issue/block/complete/correct or add updates. Workers cannot independently close approval-required tasks or modify supervisor flags.
- [ ] Reporting from task detail reuses the reporting flow with task association retained; worker reviews/confirms extraction; supervisor notified when attention is required; no repeated task search.
- [ ] Configure approaching-deadline/overdue reminder timing; notify deadline changes and updated assignments.

### Reports and conflicts: S3 §§7–8

- [ ] Separate Needs Review (critical, uncertain critical information, conflicts, missing essential facts, intervention) from Recent Activity (routine reports/observations/general updates). Routine reports require manual approval only when a configured rule demands it.
- [ ] Report detail includes original transcript/audio when retained and permitted, extracted information, worker, department/team, related task/batch, timestamp, confidence/uncertainty, evidence, full history, conflicts/corrections.
- [ ] Distinguish worker information, AI-generated suggestions, and verified facts. AI extraction is never automatically presented as verified.
- [ ] Report actions: verify, clarification request, follow-up task, corrective assignment, escalation, mark reviewed, link existing task, inspect evidence, subject to permissions.
- [ ] Conflict workflow preserves both reports, detects discrepancies, requests neutral clarification, accepts confirm/correct/context/unable-to-confirm replies, preserves clarification history, and sends significant unresolved conflicts to Needs Attention.
- [ ] Conflict detail shows both originals/transcripts/extracted values, worker identities, timestamps/evidence, clarification conversation, and status. Supervisor may confirm a report, record correction, request information, escalate, or resolve with explanation. Neither original can be silently overwritten/deleted.

### Critical alerts: S3 §9

- [ ] Alert detail includes severity, original report/transcript/evidence, worker, department/team, machine/batch/task, timestamp, AI context, acknowledgement status, escalation history.
- [ ] Alert actions: acknowledge, evidence review, corrective assignment, follow-up task, escalate, update status, record resolution.
- [ ] Preserve recommended lifecycle New → Acknowledged → Under Investigation → Action Assigned → Resolved → Verified/Closed where required. Acknowledgement never implies resolution.
- [ ] Route first to designated supervisor, notify backup under policy, escalate for expired acknowledgement window. Explicit immediate safety invokes emergency process without AI/clarification/timeout delay; the application does not replace emergency procedures.

### Workforce and team management: S3 §10

- [ ] Team overview shows department/team, assigned workers, optional lead, current shift, availability/workload; visualize team distribution, workload, shift coverage, and availability.
- [ ] Worker directory shows Employee ID/name, primary/additional departments, team, shift, account state.
- [ ] Worker creation requires full name, generated/assigned unique Employee ID, primary department; support additional departments, team memberships, skills/qualifications, shift assignment, available contact information. Do not require email. Restrict supervisor creation to authorized departments.
- [ ] Activation: account creation → Employee ID/instructions or code → worker activation → worker chooses and confirms own six-digit PIN → active. Supervisors/admins must never view PINs.
- [ ] Bulk CSV/Excel onboarding: download template → upload → validate → preview valid/invalid/duplicate/missing-field rows → explicit confirmation → create valid accounts. Never silently import invalid rows; authorized administrators may also use this workflow.
- [ ] Worker detail includes identity/memberships/shifts/skills, current tasks/workload/availability, and activity history; sensitive authentication values excluded.
- [ ] Absence management marks unavailable, identifies pending tasks, supports individual/bulk reassignment, prominently highlights critical work until reassigned, and preserves original assignment/reassignment history.
- [ ] Maintain one account per worker, one primary department, optional additional departments/teams, shift-specific assignments, visible cross-department tasks, and routing to the responsible department.

### Handovers: S3 §11

- [ ] Handover overview shows current/incoming shifts, outgoing/incoming supervisors, draft status, unresolved issues, pending task transfers, published handovers, acknowledgement status.
- [ ] Compile reports, task progress, unresolved issues, alerts, pending corrective actions, evidence, and important changes into a draft.
- [ ] Outgoing review can correct inaccuracies, add missing information, highlight critical issues, inspect unresolved tasks, and confirm responsibility transfers.
- [ ] Permit publication with unresolved issues, clearly highlighted. If outgoing supervisor fails to publish by shift end, automatically generate a provisional handover from available information, mark Pending Supervisor Review, notify incoming supervisor, and never portray it as supervisor-verified.
- [ ] Incoming experience offers concise written summary and detailed operational view; audio/listening only where supported. Provide evidence/task/conflict/transfer drill-down.
- [ ] Require separate overall receipt acknowledgement and acknowledgement of each critical issue. Neither action resolves an issue or completes a task.
- [ ] Changes after publication preserve the old snapshot, create an updated version, highlight differences, notify incoming supervisor, and retain full version/history. Never silently mutate a published handover.

### Notifications, preferences, and interaction states: S3 §§12–15

- [ ] Categorize supervisor notifications as Critical (safety/machine/serious issues/escalations), Action Required (blocked/overdue/approval/conflict/acknowledgement/evidence), Informational (routine reports/assignments/updates/handovers/team changes).
- [ ] Deliver only for authorized departments/responsibilities; critical notifications follow escalation; link directly to records, track read/unread, deduplicate events. Reading does not acknowledge operational issues.
- [ ] Settings show name, Supervisor ID, email, assigned departments/shifts, permission summary; notification/theme/language preferences; password changes, active sessions, logout. No organization policy modification or self-granted permissions.
- [ ] Every supervisor screen supports loading, useful empty/action states, error/retry, authorization restrictions, recoverable unsaved input, consequential-action confirmations, offline/sync indicators where supported, and server-confirmed success.
- [ ] Acceptance: verify invited login, independent multi-department authorization, skip/resume orientation, exception dashboard, uncertain/critical review, task/flag/team/reassignment/approval rules, conflicts, alerts, individual/bulk workforce onboarding, absences, handover publication/versions/two acknowledgement levels, relevant notifications, consequential history, responsive layouts, and light/dark modes end to end.

## Worker experience

### Navigation, identity, home: S4 §§1–3

- [ ] Provide Home, My Tasks, Report, Notifications, Profile with Report visually dominant and immediately accessible from Home. Favor minimal typing/navigation, simple language, large controls, mobile/tablet use, and Hindi/Hinglish where supported.
- [ ] Worker login uses Organization ID, Employee ID, six-digit numeric PIN, touchscreen numeric keypad, login, recovery/help; no email requirement.
- [ ] Worker activation screen accepts activation code and own six-digit PIN plus confirmation, then activates account; unique Employee ID is generated/assigned when supervisor creates the worker.
- [ ] Securely hash PINs, never display them to admins/supervisors, rate-limit login attempts, temporarily lock repeated failures, and use supervisor-assisted reset with identity verification. Support inactivity timeout, obvious logout/account switch, and additional verification for sensitive actions where necessary.
- [ ] Home header: greeting/name/current shift/date/time/avatar. Shift card: name/timing/department/team. Task summary: assigned/in-progress/urgent/approaching deadline/blocked with task-list navigation.
- [ ] Home's large Report an Update microphone provides simple speaking instructions. Show only relevant critical announcements, supervisor instructions, handover information, and task changes; no unrelated department activity or management dashboards.
- [ ] Default to primary department while surfacing relevant secondary-department tasks; prioritize urgent/critical work and deadlines without displacing the dominant reporting action.
- [ ] Implement worker task requirements in the shared task checklist above (S4 §4).

### Voice/text reporting, review, and submission: S4 §§5–7

- [ ] Reuse the same reporting workflow from Home, Report tab, and task details. Do not force selecting a task before reporting.
- [ ] Recording screen includes large microphone, active status, duration, stop, cancel, language indicator where supported, and text alternative. Flow: tap → record → stop → process/transcribe/extract → review. Clearly indicate recording; allow cancellation before submission.
- [ ] Extraction identifies operational context, description, quantity, batch/machine/task references, possible severity, missing/uncertain information, and candidate task association. Distinguish original worker input from AI-derived data.
- [ ] High-confidence task suggestions still require worker confirmation; multiple candidates get simple selection/clarification. Permit unassigned reports when no task fits and route appropriately; never lose an important report due to unresolved task association.
- [ ] Review shows original transcript with transcription correction, relevant extracted issue/quantity/batch/machine/task/department/action-taken fields, and uncertainty. Actions: edit transcript/details, confirm association, add missing information, go back, Confirm & Submit.
- [ ] Request short clarification only for important missing/uncertain information. Let workers continue with unknown values; route operationally significant uncertainty for review. AI must not invent quantities, IDs, dates, causes, or statuses.
- [ ] Potential critical safety concerns trigger the required alert workflow immediately without routine clarification delay. Preserve original report, mark uncertainty, allow later information, and never let AI severity override emergency routing.
- [ ] Submission requires explicit worker review/confirmation, backend submission, then backend success before displaying Report Submitted. Show submission reference where available, associated task, and next action. Never show server success for only local persistence.
- [ ] Text reporting uses the same extraction/review/confirmation flow; it remains available for noise, recording failure, inability to speak, or worker preference.

### Conflict clarification, notifications, handover, profile: S4 §§8–11

- [ ] Worker conflict replies: Confirm Original Report, Correct My Report, Add Additional Context, Unable to Confirm. Questions must be neutral/non-leading; do not reveal another worker's private information unnecessarily. Preserve originals, version corrections, retain history, and route significant unresolved conflict to supervisors.
- [ ] Task notifications cover new/reassigned work, description/deadline changes, approaching deadlines, overdue work. Supervisor notifications cover replies, clarification, completion rejection, and instructions; operational notifications cover relevant announcements/handovers/critical instructions.
- [ ] Notification entries include title, short description, timestamp, category, read/unread; select to open relevant record. Restrict to relevant assignments/information, prominently show critical updates, deduplicate, and configure reminder timing. Reading is not task acceptance/completion.
- [ ] Worker handover view exposes relevant previous-shift instructions, transferred tasks, unresolved affecting issues, responsibility changes, safety notices, and direct task links. Exclude confidential supervisor discussions/internal notes. Task acknowledgement and handover acknowledgement remain separate.
- [ ] Profile shows worker name, Employee ID, organization, primary/additional departments, team memberships, shift, account status. Allow own account information, permitted PIN recovery/change, and logout. Workers cannot change assigned roles or department permissions.

### Offline, shared-device security, states, accessibility: S4 §§12–16

- [ ] Permit local report creation/persistence with pending sync, retry on reconnection, and transition to Submitted only after backend confirmation. Expose Draft, Saved Locally, Pending Sync, Syncing, Submitted, Sync Failed distinctly.
- [ ] Every local report has a unique identifier; sync retries are idempotent and never duplicate reports. Failed drafts remain recoverable; locally saved never looks server-submitted.
- [ ] Show last-synchronized task data where possible, clearly distinguish stale/offline data, and do not represent server-dependent actions as successful before confirmation.
- [ ] Provide easy logout/account switching, inactivity timeout, secure local storage, no shared default PIN, and no prior-worker information left visible to the next user. Pending local reports stay securely bound to their original worker and cannot submit under another account.
- [ ] Every worker screen supports loading, useful empty/action states, understandable error, recording, processing, review distinction, submitting, connectivity/sync, server-confirmed success, and permission denial.
- [ ] Ensure large touch targets, readable high-contrast type, simple language, minimal typing, icons with labels, Hindi/Hinglish as integrations permit, responsive mobile/tablet layouts, minimal navigation, and text/icon status cues rather than color alone. Avoid management charts and complex tables.
- [ ] Acceptance: verify email-free login/activation, current shift/context, all cross-department assigned tasks, accept/start/block/ordinary completion, approval enforcement, task-linked reporting, voice/text extraction/review/correction/confirmation, clarification, non-delayed critical escalation, conflict replies, configurable deadline reminders, relevant handovers, own profile, shared-device isolation, idempotent offline sync, responsive themes, and worker-resource authorization end to end.

## Unspecified details and interpretation notes

- [ ] Choose and document numerical defaults not specified in Sections 2–4: password policy, invitation/activation expiry, session inactivity timeout, lockout threshold/duration, reminder timing, escalation response window, retention periods, and department-health thresholds. Do not attribute invented numbers to the PDF.
- [ ] Define machine/operational-area/responsibility-category representation where needed; the sections name these capabilities without prescribing a complete schema.
- [ ] Verify supported notification channels and handover audio capabilities against actual integration documentation; do not claim unsupported provider functionality.
- [ ] Resolve the optional-final-review/activation placement safely: activation gates always apply and activation remains reachable even if optional review is skipped.
- [ ] Preserve optional priority flag versus required criticality as separate concepts, or explicitly model equivalent semantics that cannot make flags mandatory or permit unapproved critical closure.
- [ ] Apply explicit master-prompt requirements when PDF wording is conditional (for example calendar view) and use its metric formulas where Section 2 defers KPI definitions.

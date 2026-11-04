# ShiftProof workflow and architecture requirements audit

Source: `SHIFTPROOF_ DOCUMENTATION.pdf`, Section 6 (Global Workflows, Business Rules & System Behaviour), Section 7 (Technical Architecture & System Design), and Section 8 (Implementation Roadmap & Development Strategy). References below use the document's section/subsection numbering. Extraction reviewed: `/tmp/shiftproof-documentation.txt`, lines 5099–6797, 7130–8358, and 8499–9511.

This is an implementation coverage checklist, not a completion claim. Every checkbox is initially unchecked. Mark an item complete only when its applicable frontend, backend, persistence, permission checks, failure handling, and acceptance tests work together. The master prompt adds requirements, particularly detailed analytics, that must also be tracked.

## 1. Core invariants

References: PDF §6.1, §6.20–22.

- [ ] Every operational transition preserves the original reporter, original information, changes, acting person, supporting evidence, unresolved conditions, and current responsible owner.
- [ ] Keep **read**, **acknowledged**, **accepted**, **in progress**, **completed**, **verified**, **closed**, **resolved**, **published**, and **provisional** as distinct states.
- [ ] Never consider AI-generated information automatically verified.
- [ ] AI cannot invent operational facts, silently overwrite reports, silently resolve conflicts, change supervisor-assigned priority, or mark work complete without appropriate confirmation.
- [ ] Preserve original reports, transcripts, corrections, and supporting evidence under their permission and retention policies.
- [ ] Persist consequential actions and their history transactionally.
- [ ] Important information cannot disappear or lose ownership as a report becomes a task, corrective action, alert, follow-up, or handover item.

## 2. Organization activation and onboarding

References: PDF §6.2–3; §8 phases 2–4. The separate role audit supplies the detailed nine-step onboarding form requirements.

- [ ] Organization registration includes official email verification before the documented activation flow.
- [ ] Save onboarding progress and allow optional configuration to be completed later.
- [ ] Activation requires at least one department.
- [ ] Activation requires at least one team or production line.
- [ ] Activation requires at least one configured shift.
- [ ] Activation requires at least one active designated supervisor or responsible person for critical alerts.
- [ ] Support multiple organization administrators.
- [ ] Never remove or deactivate the last active organization administrator.
- [ ] Deactivate departments through normal workflows instead of permanently deleting them.
- [ ] Preserve historical records when configuration or membership changes.
- [ ] Audit organization configuration changes.
- [ ] Supervisors are invited/created by an administrator; public supervisor self-registration is unavailable.
- [ ] Supervisor activation includes invitation acceptance and password creation.
- [ ] Supervisor orientation covers assigned departments, teams/workers, shift responsibilities, and handover arrangements; orientation is skippable.
- [ ] Supervisors can oversee multiple departments with explicit, independently evaluated departmental permissions.
- [ ] Worker creation/import produces activation instructions using Organization ID and Employee ID.
- [ ] Worker activation lets the worker set their own six-digit PIN.
- [ ] Workers do not need an email address.
- [ ] Each worker has one account, multiple permitted department/team memberships, and one primary department.
- [ ] Admins and supervisors cannot view or retrieve a worker's PIN.
- [ ] Worker PIN recovery requires identity verification.
- [ ] Individual worker onboarding supports employee identifier generation, skills/qualifications, department/team membership, shift assignments, availability, and absence.
- [ ] Bulk onboarding supports downloadable template, CSV/Excel upload, validation, duplicate checks, valid/invalid row preview, explicit confirmation, result summary, and activation instructions.
- [ ] Never silently import invalid rows or create duplicate employee identifiers.

## 3. Authentication, authorization and shared devices

References: PDF §6.3, §6.17–18; §7.4.2, §7.6, §7.15.

- [ ] Admin login uses verified official organization email and password.
- [ ] Supervisor login uses email, Organization ID, and password.
- [ ] Worker login uses Organization ID, Employee ID, and six-digit PIN.
- [ ] Hash passwords with an appropriate password-hashing algorithm such as Argon2id.
- [ ] Hash worker PINs securely and separately from their visible employee identifiers; never store plaintext passwords/PINs.
- [ ] Rate-limit authentication endpoints and temporarily lock repeated failed attempts.
- [ ] Support session expiration and explicit revocation.
- [ ] Worker inactivity timeout is configurable.
- [ ] Cookie sessions use secure HTTP-only cookies and CSRF protection where applicable.
- [ ] Deployed authentication and API traffic use HTTPS.
- [ ] Logout and account switching are easy to find on shared devices.
- [ ] Logout/expiration prevents the next worker from seeing the prior worker's information.
- [ ] Preserve unfinished drafts safely where possible without exposing them to another account.
- [ ] Every sensitive operation validates organization membership, role, department membership/responsibility, specific permission, and resource ownership/visibility.
- [ ] Every tenant-owned record has an organization association, and every relevant query enforces organization scope.
- [ ] Derive tenant authorization from trusted backend/session context rather than trusting client-supplied Organization IDs.
- [ ] A supervisor assigned to one department cannot access another department automatically.
- [ ] Workers can access their assigned/relevant tasks, reports, handovers, and permitted history only.
- [ ] Admin access to individual reports, audio, and transcripts follows configured privacy permissions; it is not automatically unrestricted.
- [ ] Log sensitive administrative access.
- [ ] Temporary administrative takeover is explicit, permission-scoped, visibly indicated, and audited.
- [ ] Backend authorization works independently of hidden frontend buttons or route guards.
- [ ] Explicitly test cross-organization and cross-department access denial.

## 4. Worker reporting and review

References: PDF §6.4–5; §7.7–8; §8 phases 6–8.

- [ ] Worker can start reporting immediately without selecting a task first.
- [ ] Voice workflow requests microphone permission, captures/stops recording, uploads validated audio, shows processing, generates transcript, and supports review/correction.
- [ ] Handle permission denial, unavailable microphone, recording errors, provider timeout, and processing failures.
- [ ] Provide text reporting as an alternative that remains usable when speech services fail.
- [ ] Retain the original transcript and source audio according to configured recording/retention policy.
- [ ] Extract only applicable fields: category, description, machine/equipment, line/work area, batch/order, affected quantity/unit, suggested related task, operational status, action already taken, safety/quality implications, evidence, original timestamp, and originating shift.
- [ ] Do not require every structured field for every report.
- [ ] Attempt relevant task, equipment, batch, or work-area associations without forcing a task association.
- [ ] Worker confirms suggested task association; uncertain associations are clarified.
- [ ] Accept unassigned reports and operational issues.
- [ ] Worker reviews and corrects extracted information before confirming final submission.
- [ ] Display successful submission only after backend confirmation.
- [ ] Route routine/clear reports to Recent Activity without unnecessary interruption.
- [ ] Route critical safety/quality reports to Needs Attention.
- [ ] Route uncertain critical quantities/identifiers, conflicts, essential missing information, corrective-action needs, overdue unresolved issues, missing required evidence, and pending critical handover acknowledgements to Needs Attention.
- [ ] Make AI uncertainty visible and distinguish AI classifications from supervisor decisions.
- [ ] Supervisor can verify, request clarification, assign follow-up/corrective action, or escalate a report.
- [ ] Verifying report accuracy does not automatically resolve its underlying operational issue.
- [ ] Keep underlying issues open until required action and verification are complete.
- [ ] Every submitted report remains accessible under its permission rules.
- [ ] Report history, completed task history, task-specific comments, and permitted photo/video evidence are available to workers.

### AI and clarification behavior

References: PDF §6.4–5, §6.9, §6.19; §7.7–8.

- [ ] Use Gnani speech services according to verified Prisma/Timbre capabilities and contracts; do not invent endpoints or assume interchangeability.
- [ ] Support Hindi/Hinglish and English speech only to the extent the configured provider supports them.
- [ ] Keep interface language independent from speech recognition and AI conversation language.
- [ ] Use Gemini for structured extraction/classification and approved clarification workflows.
- [ ] Validate every model result against backend schemas and business rules before use.
- [ ] Never persist arbitrary AI output directly as operational truth.
- [ ] Preserve original transcript, AI suggestions, human-confirmed information, decisions, and relevant provider/model metadata separately.
- [ ] Ask only short, relevant questions for operationally important missing/uncertain information.
- [ ] Clarification is neutral and non-leading.
- [ ] Worker can confirm, correct, add context, or explicitly indicate uncertainty.
- [ ] Stop repetitive questioning and route repeated/significant uncertainty to a supervisor.
- [ ] Do not invent quantities, identifiers, causes, statuses, or missing facts.
- [ ] Keep unnecessary sensitive information out of provider prompts.
- [ ] Provider adapters isolate vendor-specific request/response structures from business logic.
- [ ] Handle timeouts, rate limits, connection failures, malformed responses, and bounded retries without destroying unfinished reports or crashing unrelated modules.
- [ ] Provider credentials remain backend-only.
- [ ] AI cannot independently verify reports, close tasks, resolve critical conflicts, or override supervisor decisions.

**Document sequencing clarification:** PDF §6.4 places extraction before worker confirmation, while §6.5 also shows classification after storage. A compatible implementation is persisted draft/transcript → extraction → worker review → confirmed submitted report, with later classification/attention results stored separately rather than silently changing confirmed facts.

## 5. Corrections and cross-department follow-up

References: PDF §6.10–11.

- [ ] Submitted-report correction creates a new version rather than overwriting its predecessor.
- [ ] Identify the latest version and retain accessible prior versions.
- [ ] Record correction actor and timestamp.
- [ ] Significant/critical corrections notify the responsible supervisor.
- [ ] Cross-department routing preserves the originating department and original ownership.
- [ ] Create a linked follow-up in the responsible receiving department and notify its supervisor.
- [ ] Both departments can track permitted connected progress and evidence.
- [ ] Routing does not silently transfer original ownership.
- [ ] Restrict unrelated/sensitive departmental information when exposing linked follow-up records.
- [ ] Completing follow-up updates the connected original issue without losing the original report or action history.

## 6. Tasks, allocation, absence and reassignment

References: PDF §6.6–7, §6.12; §8 phases 4–5.

- [ ] Support task creation/editing, priorities, deadlines, individual/team assignment, templates, recurring work, applicable dependencies, comments, internal notes, calendar/list views, history, verification, rejection, and reassignment.
- [ ] Tasks may originate from supervisor creation, templates, recurrence, reports needing corrective action, or unfinished previous-shift work.
- [ ] Allocation evaluates department eligibility, skills/qualifications, shift availability, workload, priority, and individual/team responsibility.
- [ ] Never assign an unqualified worker merely to balance workload.
- [ ] Routine predefined tasks may use automatic allocation; specialized/new tasks require supervisor review.
- [ ] Individual task has one responsible worker.
- [ ] Team task remains one shared task, with optional lead, rather than being duplicated per member.
- [ ] Supervisor can override assignment within their permissions.
- [ ] Preserve ownership history on reassignment.
- [ ] Implement `Assigned → Accepted → In Progress → Completed → Verified → Closed` and the `Blocked` state.
- [ ] Tasks not requiring verification automatically close after completion.
- [ ] Critical tasks always require authorized supervisor approval before closure.
- [ ] Workers can view but cannot change supervisor-assigned priority.
- [ ] AI priority suggestions are visually distinct and cannot silently replace assigned priority.
- [ ] Completion rejection requires a reason, returns task to an appropriate actionable state, and notifies the worker with the reason.
- [ ] Audit all task status and priority changes.
- [ ] Acknowledging/accepting a task does not complete it; completion does not necessarily verify/close it.
- [ ] Marking worker absent identifies pending tasks and highlights critical ones.
- [ ] Absence never automatically deletes or closes tasks.
- [ ] Support single and bulk reassignment with replacement eligibility/qualification checks.
- [ ] Notify affected workers and retain previous/current ownership on reassignment.
- [ ] Supervisor-only internal notes remain inaccessible to workers.

## 7. Critical alerts and conflict resolution

References: PDF §6.8–9; §8 phase 9.

- [ ] Immediate critical safety concerns trigger alert processing without waiting for AI classification or timeout.
- [ ] Route critical alert to the designated primary supervisor.
- [ ] Route/escalate to backup after the configured non-acknowledgement window.
- [ ] Escalate to organization-level responsibility when configured criteria are met.
- [ ] Provide safe fallback routing when configuration is missing; document chosen default recipients/windows because the PDF leaves exact values unspecified.
- [ ] Alert workflow supports acknowledge, review original source, assign corrective action, track action/evidence, verify resolution, and close issue.
- [ ] Preserve original report, transcript, reporter, and timestamp for authorized responders.
- [ ] Record acknowledgement, assignment, escalation, verification, and resolution history.
- [ ] Alert acknowledgement does not resolve the underlying issue.
- [ ] Explain that ShiftProof complements, rather than replaces, the organization's emergency process.
- [ ] Detect and link related reporting discrepancies, such as different quantities for the same operational issue.
- [ ] Preserve both original conflicting reports unchanged.
- [ ] Collect traceable neutral clarification and worker confirmation/correction/context/uncertainty.
- [ ] Never force a conflict resolution or interpret uncertainty as agreement.
- [ ] Escalate significant unresolved conflicts to a supervisor.
- [ ] Supervisor can inspect both reports, transcripts, clarification responses, and evidence.
- [ ] Record final supervisor decisions and complete correction/resolution history.

## 8. Handover lifecycle and versioning

References: PDF §6.13–14; §8 phase 10.

- [ ] Compile department handover drafts from reports, unresolved issues, critical alerts, pending tasks, blocked/completed work, corrective actions, evidence, and outstanding acknowledgements.
- [ ] Outgoing supervisor can review, correct/add missing information, inspect unresolved items, and publish.
- [ ] Published handover may contain unresolved items, which remain prominently identified and open.
- [ ] If shift ends before publication, generate a provisional handover marked **Pending Supervisor Review** and notify incoming shift.
- [ ] Provisional handover never appears supervisor-verified.
- [ ] Supervisor can review/update the provisional handover through the normal publication/version workflow.
- [ ] Deliver one consolidated handover per department to the incoming department team.
- [ ] Additionally route individual unresolved responsibilities to appropriate incoming supervisors.
- [ ] Primary supervisors receive handovers first; involve backups according to configuration.
- [ ] Incoming view exposes priority summary, critical issues, pending tasks, and source details; support listening where the verified provider capabilities permit.
- [ ] Overall handover acknowledgement and individual critical-item acknowledgement are separate operations.
- [ ] Every acknowledgement records actor/recipient, timestamp, and exact handover version; critical-item acknowledgement also identifies the item.
- [ ] Acknowledgement means receipt and does not resolve or close unfinished work.
- [ ] Published versions are immutable.
- [ ] Important new information creates a new version and identifies additions/changes.
- [ ] Notify incoming recipients about new versions.
- [ ] Previous versions remain accessible, and the latest published version is obvious.
- [ ] Handover items retain links to original reports, tasks, actions, and evidence.

## 9. Notifications, scheduling and durable processing

References: PDF §6.15; §7.9, §7.12, §7.14.

- [ ] Persist notifications for task assignment/reassignment, approaching deadlines, overdue work, critical alerts, clarification requests, conflict handling, handover publication/version changes, pending critical acknowledgements, escalation, and affected organization configuration issues.
- [ ] Target relevant workers/supervisors; admins receive administrative/configuration issues and escalations rather than routine task activity.
- [ ] Deep-link every notification to its source operational record.
- [ ] Keep notification read/unread distinct from operational acknowledgement.
- [ ] Deduplicate notification events.
- [ ] Notification delivery failures cannot silently change task, issue, alert, or handover status.
- [ ] Make deadline reminder timing and escalation windows configurable.
- [ ] Provide in-app notifications and email for selected invitation/administrative workflows; push where supported and other channels only where required by organization policy.
- [ ] Use SSE/WebSockets where materially useful for critical alerts, assignments, clarification requests, and handover updates.
- [ ] Persistent database records remain notification source of truth; reconnect/offline users retain missed notifications.
- [ ] Schedule upcoming deadline checks, overdue checks, shift transitions, provisional handovers, pending acknowledgement checks, and alert escalation.
- [ ] Schedule according to organization timezone and configured shift timing while storing timestamps consistently in UTC.
- [ ] Run transcription, extraction, evidence processing, handover compilation, delivery, reminders/escalations, and scheduled reports asynchronously where appropriate.
- [ ] Persist traceable job lifecycle: created/queued → processing → success/failure → persisted result.
- [ ] Log job failures, bound retries, and make retried operations idempotent where possible.
- [ ] Critical processing must not rely only on in-memory FastAPI background tasks; use persistent production job state/worker queue.

## 10. Offline synchronization

References: PDF §6.16–17; §7.13; §8 phase 11.

- [ ] Use IndexedDB for local drafts, pending reports, and pending uploads; service worker may cache the application shell.
- [ ] Display distinct states: `Draft`, `Saved Locally`, `Pending Sync`, `Syncing`, `Submitted`, and `Sync Failed`.
- [ ] Generate a unique client request identifier/idempotency key for each offline submission.
- [ ] Backend atomically creates a report or returns the existing record for a retried submission.
- [ ] Retry never creates duplicate reports.
- [ ] Preserve original creation timestamp and originating shift during delayed synchronization.
- [ ] Mark Submitted only after backend confirmation.
- [ ] Clearly show connectivity, synchronization progress, failure, and retry.
- [ ] Retry after network restoration and allow recovery from failed synchronization.
- [ ] Protect sensitive local content and isolate queues by user and tenant.
- [ ] Never upload one user's pending report under another user's session.
- [ ] Logout/session expiry clears access while safely preserving unfinished reports where possible.
- [ ] Offline retries cannot create inconsistent server records or bypass normal authorization/validation.

## 11. Logical data model and persistence

References: PDF §7.4–5. This is a proposed logical model; equivalent normalized structures are acceptable, and every logical entity does not necessarily require its own physical table.

- [ ] Identity/organization: Organization, User, Role/UserRole, Department, Team, TeamMembership, DepartmentMembership, SupervisorAssignment, OrganizationInvitation.
- [ ] Workforce: EmployeeProfile, EmployeeCredential, Shift, ShiftAssignment, ShiftSchedule, Skill, WorkerSkill, WorkerAvailability.
- [ ] Tasks: Task, TaskAssignment, TaskStatusHistory, TaskPriorityHistory, TaskTemplate, TaskComment, TaskInternalNote, TaskVerification, TaskDependency.
- [ ] Reporting: Report, ReportVersion, Transcript, AIExtraction, AIInteraction, ReportTaskLink, ReportEvidence, ReportClassification.
- [ ] Exceptions: Conflict, ConflictReport, ConflictClarification, ConflictResolution, Alert, AlertAssignment, AlertAcknowledgement, EscalationRule, EscalationHistory.
- [ ] Handovers: Handover, HandoverVersion, HandoverItem, HandoverRecipient, HandoverAcknowledgement, HandoverItemAcknowledgement.
- [ ] Platform: Notification, NotificationPreference, AuditLog, FileAsset, OrganizationPolicy, DeviceSession, BackgroundJob.
- [ ] Use stable primary identifiers, foreign keys, database constraints, and appropriate query indexes.
- [ ] Use PostgreSQL for production and integration validation; SQLite is permitted for lightweight local development.
- [ ] Manage schema changes with Alembic migrations and SQLAlchemy models.
- [ ] Use transactions for critical multi-record updates.
- [ ] Preserve required historical records with explicit report/handover versions and soft deactivation.
- [ ] Avoid unnecessary duplication of task/report data.
- [ ] Store timestamps consistently in UTC and display them in organization/user timezone.

## 12. Files, evidence, privacy and audit

References: PDF §6.18; §7.10, §7.15.

- [ ] Support audio, photographs, videos, and permitted supporting documents.
- [ ] Store binary files in private storage and metadata/access references in the database.
- [ ] Validate file type and size in the frontend and backend, with backend checks authoritative.
- [ ] Secure upload handling and authorize every evidence access.
- [ ] Link evidence to the appropriate report/task and preserve source ownership.
- [ ] Use short-lived signed URLs where appropriate; no public access to private recordings.
- [ ] Enforce configurable recording/evidence retention policies.
- [ ] Apply malware scanning where appropriate for supported document uploads.
- [ ] Audit account creation/deactivation and role/permission changes.
- [ ] Audit department/team changes, task creation/assignment/reassignment, and task priority/status changes.
- [ ] Audit report submissions/corrections, conflict clarification/resolution, and alert acknowledgement/escalation.
- [ ] Audit handover publication/version changes and overall/critical-item acknowledgement.
- [ ] Audit sensitive access, administrative takeover, and organization policy changes.
- [ ] Audit entries identify actor, action, timestamp, and relevant resource.

## 13. API, configuration and reliability

References: PDF §7.11, §7.15–19, §7.21–22; §8 phases 0–2 and 13.

- [ ] Use versioned REST APIs under `/api/v1` with consistent schemas, pagination/filtering, errors, and authorization rules.
- [ ] Cover authentication, organizations/departments/teams/shifts, workforce/import/absence/PIN recovery, tasks/actions, reports/transcription/extraction/corrections/clarifications/evidence, conflicts, alerts, handovers/versions/acknowledgements, notifications/preferences, analytics, and audit.
- [ ] Treat PDF endpoint names as proposed contracts; preserve existing frontend compatibility through adapters/aliases where necessary.
- [ ] Separate HTTP routes, validation schemas, services/business rules, persistence/repositories/models, and provider integrations.
- [ ] Centralize authentication, tenant scope, and authorization.
- [ ] Centralize frontend API communication and authenticated state; provide three distinct role layouts.
- [ ] Validate environment configuration at startup and separate development, test, staging, and production data/configuration.
- [ ] Keep real credentials out of source and frontend bundles; supply `.env.example` and environment/secrets-manager configuration.
- [ ] Log requests/errors, authentication, critical workflow events, provider failures, and background failures without exposing credentials or unnecessary sensitive data.
- [ ] Observe API availability/latency, database connectivity, queue health, external provider availability, failed synchronization, and delivery failures.
- [ ] Provider failures do not crash unrelated operational modules.
- [ ] Preserve understandable user-facing errors and operational data on failure.
- [ ] Production deployment includes HTTPS, PostgreSQL, persistent files/jobs, secure secrets, logging/monitoring, error tracking, migrations, health checks, backups, and recovery procedures.
- [ ] Provide repeatable Docker-based local/deployment setup; Kubernetes is not required for the initial system.

## 14. Analytics and reporting

References: PDF §8 phase 12, §6.18, §7.21. The master prompt extends this list with precise metric, filter, and visualization requirements.

- [ ] Provide organization overview, department summaries, task performance, workload, issue trends, quality/safety trends, shift comparisons, handover performance, workforce activity, audit history, and configurable reporting.
- [ ] Use charts, trends, progress indicators, comparisons, drill-downs, and time summaries; plain statistics alone are insufficient.
- [ ] Use actual backend data exclusively and display appropriate empty states when data does not exist.
- [ ] Define metric calculations and cohorts; compare compatible time periods and denominators.
- [ ] Enforce organization, role, department, and sensitive-data permissions in analytics.
- [ ] Preserve report corrections as versions rather than counting them as independent new reports.
- [ ] Track the complete detailed workforce, task, safety, quality, reporting, handover, and supervisor-operations metric/filter requirements from the master prompt in the product coverage matrix.

## 15. Acceptance tests and definition of done

References: PDF §6.21; §7.16, §7.21; §8 phases 1–13 and §§6–7.

- [ ] Verified admin registration, resumable mandatory onboarding, activation prerequisites, and final-active-admin protection pass end to end.
- [ ] Supervisor invitation/activation and department-specific permissions pass.
- [ ] Worker creation, PIN activation/login/recovery, individual/bulk onboarding, multiple memberships, and qualifications pass.
- [ ] Bulk import preview/confirmation, duplicate detection, invalid-row handling, and partial/failing input scenarios pass.
- [ ] Cross-tenant/cross-department denial, role restrictions, privacy restrictions, revocation/expiry, and PIN lockout pass.
- [ ] Task individual/team ownership, allocation eligibility, state transitions, critical approval, rejection reasons, comments/internal-note visibility, recurrence, and dependencies pass where applicable.
- [ ] Worker absence/reassignment preserves ownership and status history and notifies affected users.
- [ ] Voice/text reporting works without mandatory task selection, with review/correction, unassigned reports, evidence, and backend-confirmed submission.
- [ ] Provider timeout/rate-limit/malformed-result failures preserve reports; AI cannot approve/close operations.
- [ ] Report correction history is immutable, versioned, and appropriately notified.
- [ ] Immediate critical alert routing, primary/backup escalation, and acknowledgement-versus-resolution pass.
- [ ] Conflict evidence preservation, clarification history, supervisor decisions, and cross-department follow-up pass.
- [ ] Draft/publication/provisional handovers, source links, immutable versions, version-specific overall acknowledgement, and individual critical acknowledgement pass.
- [ ] Offline persistence, visible sync states, retries/idempotency, and shared-device queue isolation pass.
- [ ] Notifications persist, deep-link correctly, deduplicate, survive delivery failure, and remain separate from operational acknowledgement.
- [ ] Durable background processing retries and scheduling respect organization timezone and retain job history.
- [ ] Analytics use real permitted data and documented calculations/cohorts.
- [ ] Frontend navigation, validation, loading/error/empty/offline states, accessibility, mobile/tablet layout, English, and Hindi pass.
- [ ] Database transaction behavior and migrations pass in the deployment environment.
- [ ] Backup and recovery procedures are tested; health/error visibility and external failure handling are verified.
- [ ] Document setup/deployment/integration requirements and update module status only after actual acceptance checks.
- [ ] Do not mark disconnected mocked screens or rendered dashboards as completed product features.

## 16. Future-work distinctions and unspecified details

References: PDF §8.4, §8.5–10.

- [ ] Preserve every essential requirement from Sections 1–7 even if technically difficult; do not relabel such features post-MVP merely to defer them.
- [ ] Build foundational dependencies before dependent modules: identity/database → organization/workforce → tasks/reporting → provider processing/supervisor review → alerts/conflicts → handovers/notifications/offline → analytics.
- [ ] Track advanced workload optimization, sophisticated automatic allocation, advanced analytics/conflict/escalation features, extensive exports, additional languages/integrations, richer collaboration, and forecasting as the document's post-MVP enhancement categories.
- [ ] Do not invent unspecified forecasting algorithms, new vendor integrations, additional-language guarantees, or claim them implemented without defined behavior and verification.
- [ ] Document chosen operational defaults where the PDF leaves them unspecified, including fallback alert routing/windows, exact lockout/session parameters, retention defaults, and the actionable state after rejected completion.
- [ ] Treat the proposed data model, endpoint paths, and illustrative AI response schema as implementation guidance rather than falsely claiming every example is a fixed wire contract.
- [ ] Record live provider documentation/credential limitations honestly; an adapter boundary is not equivalent to a verified provider integration.

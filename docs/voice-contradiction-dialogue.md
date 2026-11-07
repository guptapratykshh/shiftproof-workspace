# Integrated report conversations

The existing Report page now runs recording → Gnani transcription → Gemini extraction → scoped comparison → a spoken clarification. Workers answer in the same page, check the final count and press **Confirm and send**. A spoken answer never submits a report or resolves a discrepancy.

## Using the flow

1. Owners can open **Departments → Linked department transfers** and add a directional link, such as Manufacturing → Receiving. Only active links allow comparisons across departments. The receiving department owns supervisor resolution.
2. Worker A reports 100 manufactured pieces against a batch or transfer reference.
3. Worker B records receiving 85 pieces against the same reference. ShiftProof asks about the 15-piece difference using Gnani speech and shows the same question as text.
4. B uses **Reply**, **Type answer**, or **I’m not sure**. A confirmed 85 stays 85. An explicit correction updates the draft. An explanation about the remaining 15 is preserved for review; it does not silently resolve the gap.
5. After B checks the report and presses **Confirm and send**, A receives a clarification and supervisors receive a verification notification. B’s already-given answer is retained. A can use the same voice controls on their report. The receiving department’s authorized supervisor records the resolution.

Same-worker comparisons identify the earlier statement as the worker’s own. Different workers’ names, full reports and recordings are not disclosed in the question. Manufacturing and receiving quantities remain distinct stages; their difference is a transfer question, not proof of an incorrect report.

## Persistence and interfaces

MongoDB remains the primary store. `report_conversations`, `conversation_turns` and `department_links` are registered with the existing MongoDB bootstrap, validators, unique indexes and organization/author scope. The compatible Alembic migration is for supported relational test/deployment configurations; historical report rows are not rewritten.

- `POST /api/v1/report-conversations`: create an idempotent draft session, optionally answering an existing clarification.
- `GET /api/v1/report-conversations/{id}`: read the requesting worker’s retained session and ordered turns.
- `POST /api/v1/report-conversations/{id}/turns`: accept typed or recorded turns with a revision and idempotency key; return asynchronous state.
- `/api/v1/department-links`: owner-managed directional comparison links.
- Report submissions accept optional `conversation_id` and `conversation_revision`; existing callers retain their contracts and idempotency.

The existing queue handles `conversation_transcribe`, `conversation_analyze` and `speak` jobs. Each result is tied to a revision. Source report versions and comparison evidence remain server-side. Submission checks the reviewed draft and current source versions again, inside the existing department serialization boundary. A changed source returns the worker to checking before a report can be submitted.

Nullable report fields distinguish `quantity_stage`, `transfer_reference` and `transfer_complete`. Explicit transfer references can connect observations across shifts; other comparisons retain the existing entity, time, unit and counting-basis rules. Different work areas in linked departments do not hide a matching transfer. Spoken identifier prefixes and number words are normalized without merging different identifiers.

## Failure and access behavior

Questions are constructed from validated comparisons. Gemini interprets an answer into suggestions, never decides which worker is right. Each conversation asks at most three clarification questions before retaining unresolved details for supervisor review.

Recording remains limited to 29 seconds. Playback stops before microphone capture. Browser-blocked autoplay shows **Tap to hear the question**; interrupted audio downloads can be retried. Typed answers and recordings are saved through the existing encrypted local-draft storage. Offline or provider failures show checking as unavailable. Immediate safety alerts remain available independently.

Editing stops obsolete playback and invalidates confirmation. Late results cannot overwrite newer text. Access is checked again by queued jobs. Cross-department reviewers see only permitted source reports plus limited comparison facts from linked departments. Only the receiving department’s reviewer can resolve a cross-department conflict.

Conversation content and job results follow transcript retention. Expired sessions cannot be reopened; scheduled retention removes conversation text and internal details while preserving the audit/reference structure.

## Running and reviewing

Use the existing private `backend/.env` Gnani and Gemini settings. No additional speech provider or key is needed. Run `python -m app.bootstrap` with the backend environment after pulling, then restart the API and worker. The current local primary database has the new collections; local preview processes reload the changed backend.

Automated coverage is in `backend/tests/test_conversations.py`, the opt-in synthetic provider check `backend/tests/test_dialogue_live.py`, and `integration/dialogue.spec.ts`. The latter replaces browser tests for the retired separate transcription/readback controls and checks the integrated three-role flow, blocked playback, microphone denial and late results.

The live-provider test requires `SHIFTPROOF_LIVE_DIALOGUE=1`; it sends only fictional test speech. MongoDB test runs require an empty, dedicated `shiftproof_test_…` database, never the application database. Browser captures are saved under `test-results/dialogue` and copied to the local review gallery in `.sites-runtime/dialogue-review`.

## Validation recorded on 7 November 2026

- Complete backend suite: 149 passed, 5 opt-in cases skipped. The final targeted conversation/contradiction run, including the added spoken-transfer regression, passed all 96 cases.
- Existing contradiction browser scenarios: 42 passed.
- Public browser suite: 17 passed.
- Workspace and mail browser suite against the production build: 10 passed, including offline-shell behavior, all role layouts, Hindi and both themes.
- Synthetic live Gnani STT/TTS plus Gemini answer interpretation: passed against an isolated MongoDB database. The test database was removed after verification. The application database was not populated with test reports.
- Production build and TypeScript checks passed. Existing bundle-size/dependency-comment warnings remain.

Live services can fail transiently; an earlier STT attempt and an isolated Atlas test bootstrap failed. The final live conversation completed successfully, and the app retains the explicit unavailable/retry path. This verification is not a promise of uninterrupted provider availability.

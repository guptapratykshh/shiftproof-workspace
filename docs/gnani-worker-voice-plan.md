# Gnani worker voice implementation plan

Branch: `feat/gnani-worker-voice`. Research checked 6 November 2026.

## Outcome

A worker should be able to speak a short update, check the words and important
details, optionally hear them, and deliberately send the report. Retain the
existing typed and offline paths. Use the existing private `GNANI_API_KEY` for
both Prisma v3.0 and Timbre v3.0; no additional provider account is required.
Gemini continues to suggest structured fields only when requested. Neither
speech model decides whether work is complete or a safety condition is resolved.

## Research and decisions

- [Prisma REST](https://docs.gnani.ai/api/STT/speech-to-text): short recordings,
  multilingual hints, code-mixed text and vocabulary context fit our report
  workflow. Keep the 29-second recording limit, below the endpoint limit.
- Send a small, authorized department vocabulary using `keyterms` and `topic`.
  A selected task can contribute equipment/work-area terms only after access
  checks. Never inject another worker's task or replace quantities automatically.
- [Prisma streaming](https://docs.gnani.ai/api/STT/stt-websocket) is a future
  enhancement, not a dependency: mobile interruptions, reconnects and final versus
  provisional transcripts need separate validation. REST retains recoverable
  source audio and is already working with this account.
- [Timbre REST](https://docs.gnani.ai/api/TTS/tts-inference): explicitly configure
  a model-compatible voice, language and normal speed. Validate returned WAV data.
  Use readable, deterministic scripts; do not truncate away unresolved conditions.
- Live testing found a 2,164-character handover request returning HTTP 500. Split
  scripts into sequential sections of at most 650 characters, preferably at
  sentence/paragraph boundaries, then join complete PCM audio into one player.
  This is an application choice, not a documented provider text limit. Normalize
  the streaming WAV length sentinel observed from the provider. Reject malformed,
  truncated declared-length or mismatched audio; never publish only part of a script.
- TTS speaks the supplied text; it is not a translator. Localize labels in Hindi
  or English and preserve the worker's original words and quantities. Mixed text
  uses automatic language routing. Avoid dramatic expression tags for reports.
- [Challenge rules](https://www.gnani.ai/internship): demonstrate genuine model
  use and measurable behavior. Public engagement affects the shortlist; no
  feature or benchmark guarantees an interview. Use fictional demonstration data.

## Worker interaction

1. **Speak:** preselect the worker's department when available; show language and
   consent, one large microphone control, a visible timer, Stop and Cancel.
   Explain that stopping generates text online. Cancel discards this recording.
2. **Check:** automatically upload and transcribe after Stop. Preserve the local
   draft first. Show a nearby, announced processing status and a retry action on
   failure. Keep typing available. Existing report fields remain accessible under
   an optional details disclosure, opened when AI suggestions need review.
3. **Listen:** an optional readback reads the current update and populated fields,
   including unresolved conditions and questions. Do not autoplay. A visible audio
   player supports pause/replay; spoken playback is not proof of understanding.
4. **Send:** explicit review confirmation remains mandatory. Any edit invalidates
   confirmation and previously generated readback. No voice command submits a
   report, acknowledges a handover or resolves a task.

Immediate safety alerts remain independently accessible without waiting for AI.
Hindi copy, keyboard focus, mobile wrapping and 44px touch targets are part of the
implementation, not follow-up polish. Keep the plum/lavender theme.

## API and data

- Authenticated voice capabilities expose availability, never credentials.
- Transcription accepts an optional selected task ID and validates it against the
  recording department and the caller's access. Context is derived server-side.
- Add an authenticated report-readback job endpoint. Validate text/fields and
  department membership; build a deterministic script and reject overlong audio
  requests clearly instead of dropping text. Deduplicate by actor, script,
  language and synthesis settings. Never store a submitted report as a side effect.
- Existing `speak` jobs handle both draft readback and versioned handover audio.
  Generated audio stays private to the requester under existing evidence rules.
  Record the exact script and synthesis metadata with the job result.
- Recheck access before processing queued audio. Preserve handover version
  identity and invalidate playback when the viewer changes versions.
- Keep provider errors actionable and secret-free, with saved drafts and retry.
  Distinguish no speech from provider failure. Configuration readiness alone is
  not a successful-call health claim.

## Race and failure handling

- Ignore transcription/extraction responses for an older input revision. A slow
  response must not overwrite text edited while the request was in flight.
- Stop media tracks on cancel, permission failure and navigation. Navigation must
  not turn an unfinished recording into a new provider request.
- Disable duplicate processing and sending while capture/processing is active.
- Reset readback immediately after edits; revoke audio object URLs on replacement
  and unmount. A late download cannot reintroduce an obsolete recording.
- Offline recording remains a saved local draft. Retry transcription when online;
  never claim that offline STT or TTS has run.

## Verification and delivery

Backend checks: provider request contract, both scopes with synthetic live samples,
empty audio, authentication/department isolation, task-context isolation, readback
idempotency, preserved negation/quantity, no report side effect, playback privacy,
and revoked queued access. Retain existing grounding and workflow tests.

Browser checks: automatic recording-to-text, cancel, denied microphone, offline
retry, late response after editing, readback replacement, explicit confirmation,
handover version changes, Hindi/light and English/dark, narrow mobile and desktop.
Run the production build and existing workspace suite. Save review captures.

Measure real end-to-end latency separately from vendor processing time. A future
evaluation should use consented fictional Hindi/Hinglish/English updates and
label simulated noise/telephone conditions. Do not invent accuracy percentages or
advertise an unmeasured noise benchmark.

Commit frontend files as `the-ivii`, backend/docs as `guptapratykshh`, one file per
commit with lowercase one-line messages and no coauthor trailers. Push this branch
for review; keep `main` unchanged. Secrets stay in ignored local environment files.

## Results on 6 November 2026

- The existing workflow/integrity tests and initial voice tests passed together
  (41 tests). The final focused voice suite passed 12 cases, including long-script
  preservation, streaming WAV normalization and failure without partial playback.
- The production build and existing workspace/mail browser suite passed (10 tests).
  After adding recovery from interrupted private audio downloads, the two voice
  browser tests passed again against a fresh production build. Desktop and Hindi
  mobile review captures are saved under `.sites-runtime/voice-review/`.
- The same configured key completed live Prisma transcription, short English and
  Hindi Timbre synthesis, authenticated draft readback and versioned handover audio.
  No operational report or handover acknowledgement was submitted by these checks.
- The shared workspace also contains another session's report-field and
  contradiction work. Voice commits exclude those changes. Other machines using
  the same database need compatible API/worker code before testing the new jobs.
- Real-time streaming, voice cloning, automatic free-text translation and a
  measured noisy-factory accuracy benchmark are not implemented by this pass.

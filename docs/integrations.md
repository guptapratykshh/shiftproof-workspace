# Integration configuration and verification

Credentials belong in native `backend/.env` or the deployment host's private root `.env`. They must never be in frontend variables, source files, screenshots or logs. Native API and worker processes run from `backend`; a project-root `.env` alone does not configure them. Restart both processes after changing credentials. Synthetic live speech, playback and extraction checks are described below; production hosting and object storage still require separate verification.

## Gnani Prisma speech-to-text

`backend/app/integrations/gnani/client.py` uses the documented `POST https://api.vachana.ai/stt/v3`, `X-API-Key-ID`, multipart `audio_file`, `model`, `language_code` and `format`. Set `GNANI_API_KEY` and an entitled `GNANI_STT_MODEL` (default `prisma-v3.0`). FFmpeg converts validated recordings to mono 16 kHz WAV; the recording flow supports Hindi, English and the provider's codemix path. The adapter requires a successful structured result containing a nonempty transcript.

Stopping a recording saves a private local draft and requests transcription when connected. Empty speech results produce a re-record/type prompt without creating an empty transcript. Department and optional selected-task vocabulary are derived server-side after access checks and sent as `keyterms`/`topic`. Late results cannot replace text edited while processing. Offline capture remains a draft; it does not run an offline speech model.

Source: [Gnani speech-to-text API](https://docs.gnani.ai/api/STT/speech-to-text).

Verification with an authorized account: record a short consenting sample in each intended language, confirm that the original transcript/model are retained, edit it, run extraction and confirm the final report. Check quota/timeout/invalid-response behavior. Automated tests already cover timeout, rate limiting, server failure and malformed payloads. Missing credentials show a text-entry alternative; a queued or failed transcription never becomes a submitted report.

## Gnani Timbre handover audio

The adapter uses `POST https://api.vachana.ai/api/v1/tts/inference`, the same `GNANI_API_KEY`, and `GNANI_TTS_MODEL` (default `timbre-v3.0`). `GNANI_TTS_VOICE` defaults to `Shivani`; `GNANI_TTS_SPEED` defaults to 1.0 and accepts 0.85–1.15. Use a voice belonging to the selected model. The request explicitly supplies language and asks for mono 16 kHz PCM WAV output. Both English and Hindi samples produced valid WAV files with the existing account on 6 November 2026. Authenticated worker transcription, draft readback and a 2,164-character versioned handover also passed live checks.

`POST /report-readback` generates optional private audio of the current text and populated fields without submitting a report. Scripts retain negation, quantities, safety concerns and unresolved questions. Edits clear obsolete playback and review confirmation. `POST /handover-audio/{version_id}` reads the frozen handover version and rechecks access before processing. Scripts over the application's 5,000-character limit are rejected with a readable alternative rather than silently truncated. Spoken playback does not confirm receipt, close work, translate free text or prove that a person understood it.

Longer scripts are split at sentence/paragraph boundaries where possible, with at most 650 characters per provider request. Requests run sequentially and their complete PCM frames are joined into one WAV player. The adapter normalizes the streaming length sentinel observed in Gnani's WAV response; declared-length WAV files must be complete and all sections must share the same audio format. A failed section fails the job without publishing partial playback. This is an application workaround for an observed HTTP 500 on a longer request, not a claimed documented Gnani text limit. A 120-second synthesis budget is checked between calls and limits request timeouts; the written script always remains available.

Source: [Gnani TTS inference API](https://docs.gnani.ai/api/TTS/tts-inference).

The written version remains available if generation fails. The authenticated `/voice/capabilities` endpoint indicates configuration availability, not a provider health or audio-quality guarantee. No speaker identification, voice cloning, diarization or measured noise-robustness claim is made. See [the implementation plan](gnani-worker-voice-plan.md) for the worker interaction and verification scope.

Run matching API and worker versions on every machine sharing the same database. An older worker can claim a new voice job and process it using the older adapter. Live verification on this branch executed the synthetic jobs with the current worker implementation; it does not verify other developers' processes.

Cached speech now checks whether the generated file is present and complete before reuse. A missing or truncated generated file can be rebuilt from its retained script through the playback endpoint or **Try listening again**. Local recovery reserves the existing job and runs after commit on the API server's filesystem, so another machine cannot claim that repair while its lease is active. Healthy audio is reused, storage outages remain visible, and deleted/expired audio or revoked source access blocks regeneration. Original recordings and handover acknowledgements are unchanged. On 7 November 2026, both affected local handover recordings were rebuilt and the reported handover played successfully through the Cloudflare URL in Chrome. Recovery, retention, provider-failure and browser retry checks passed.

## Gemini structured extraction

Set `GEMINI_API_KEY` and an available `GEMINI_MODEL` (default `gemini-2.5-flash`). `backend/app/integrations/gemini/client.py` uses the official Google SDK and a structured response schema for report fields. It retains uncertainty, validates identifiers/numbers against the source and rejects unsupported task IDs. Task association suggestions are restricted to actual visible tasks and always require worker confirmation.

Source: [Google structured-output documentation](https://ai.google.dev/gemini-api/docs/structured-output).

AI has no authority to close tasks, verify reports, resolve conflicts or override an immediate safety concern. Verify your account's model entitlement, mixed-language quality and malformed-output behavior with non-sensitive consented samples before operational use. Only a worker-confirmed report is submitted; provider output alone is never a factual record.

## Email

Native development uses `MAIL_MODE=file`; jobs write private `.eml` files under `backend/data/outbox/`. Docker development uses Mailpit at http://localhost:8025. Both capture mail locally. Production requires `MAIL_MODE=smtp` (forced by the base compose configuration), `SMTP_HOST`, `SMTP_PORT`, optional `SMTP_USER`/`SMTP_PASSWORD`, `SMTP_STARTTLS`, and an authorized `MAIL_FROM` sender. The supplied production override defaults to port 587 and STARTTLS. It does not implement implicit TLS on port 465.

Verify domain authorization and delivery using your own account before inviting others. An API registration response indicates a queued verification email, not confirmed inbox delivery. Inspect administrator Settings → background jobs for failures; no secrets or raw email token payloads are displayed there.

Signup and recovery responses include `delivery: local_outbox | smtp_queued`. The interface explicitly identifies local capture, or says the email is queued; it never treats queue acceptance as confirmed inbox delivery. SMTP STARTTLS uses certificate and hostname verification. Authenticated SMTP configuration requires a password.

For Gmail, configure the ignored `backend/.env` with `MAIL_MODE=smtp`, `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`, `SMTP_STARTTLS=true`, your full Gmail address as `SMTP_USER`, and `MAIL_FROM="ShiftProof <your-account@gmail.com>"`. Store a Google App Password privately as `SMTP_PASSWORD`, without display spaces. Google requires 2-Step Verification for App Passwords; see [Google's App Password instructions](https://support.google.com/mail/answer/185833?hl=en) and [SMTP settings](https://support.google.com/mail/answer/7104828?hl=en). Restart both API and worker after changes. Never put SMTP credentials in frontend `VITE_` variables or source control.

Local Gmail SMTP authentication and a real verification send were checked on 1 November 2026. The worker's `smtp_accepted` result confirms the SMTP server accepted the message; inbox placement still depends on the recipient's mail system. Local verification links must be opened on the computer running ShiftProof.

## Evidence storage and PDF scanning

Private local disk is the default. Native files are under `backend/data/evidence`; Docker uses its named evidence volume. Photos are decoded/re-encoded and metadata removed; audio/video is checked using ffprobe. Uploads have size limits, MIME/content checks, consent gates and tenant/department authorization. Audio consent is required independently of optional onboarding customization.

Optional `STORAGE_MODE=s3` requires `S3_BUCKET`, optional `S3_ENDPOINT_URL`, and AWS-compatible credentials. Objects request server-side AES256 encryption. Configure a private bucket, prohibit public access, use scoped credentials, and test upload/download/retention with a consented sample. API downloads reauthorize the requester; public bucket URLs are not exposed.

PDFs additionally require `MALWARE_SCANNER` pointing to a compatible ClamAV executable. Native example: install ClamAV, update definitions with `freshclam`, and set `MALWARE_SCANNER` to the absolute `clamscan` path. The backend image includes the executable but no pretrusted signature database. Mount maintained definitions at `/var/lib/clamav:ro` in both API and worker containers and set `MALWARE_SCANNER=/usr/bin/clamscan`. Keep definitions updated outside the unprivileged app process. Blank configuration, missing definitions, scan failure or a timeout rejects the PDF; it never silently bypasses scanning.

Production-host SMTP, S3 and scanner success paths still need environment-specific verification. Automated evidence tests cover private photo access, tenant/account restrictions, upload validation and retention.

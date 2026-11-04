# Integration configuration and verification

Credentials belong in native `backend/.env` or the deployment host's private root `.env`. They must never be in frontend variables, source files, screenshots or logs. The adapters are implemented; this delivery has **not** made live calls to a paid speech/AI account or production mail/object storage.

## Gnani Prisma speech-to-text

`backend/app/integrations/gnani/client.py` uses the documented `POST https://api.vachana.ai/stt/v3`, `X-API-Key-ID`, multipart `audio_file`, `model`, `language_code` and `format`. Set `GNANI_API_KEY` and an entitled `GNANI_STT_MODEL` (default `prisma-v3.0`). FFmpeg converts validated recordings to mono 16 kHz WAV; the recording flow supports Hindi, English and the provider's codemix path. The adapter requires a successful structured result containing a nonempty transcript.

Source: [Gnani speech-to-text API](https://docs.gnani.ai/api/STT/speech-to-text).

Verification with an authorized account: record a short consenting sample in each intended language, confirm that the original transcript/model are retained, edit it, run extraction and confirm the final report. Check quota/timeout/invalid-response behavior. Automated tests already cover timeout, rate limiting, server failure and malformed payloads. Missing credentials show a text-entry alternative; a queued or failed transcription never becomes a submitted report.

## Gnani Timbre handover audio

The adapter uses the documented `POST https://api.vachana.ai/api/v1/tts/inference`, the same key header and `GNANI_TTS_MODEL` (default `timbre-v3.0`). It requests WAV output and accepts a valid RIFF/WAVE response. If your account returns another documented envelope, validate that contract and adapt the decoder before enabling it. Audio is created from an authorized handover version and stored as private evidence.

Source: [Gnani TTS inference API](https://docs.gnani.ai/api/TTS/tts-inference).

Live verification is pending. The written version remains available if generation fails. No claims of speaker identification, diarization or unsupported provider features are made.

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

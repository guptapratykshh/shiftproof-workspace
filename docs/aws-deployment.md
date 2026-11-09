# AWS deployment and recovery

Deployment date: 9 November 2026. Public application: **https://shiftproof.duckdns.org**. The original **https://13.203.164.49** address remains available.

## What is running

The `shiftproof-live` CloudFormation stack in Mumbai (`ap-south-1`) owns an isolated VPC, one `t3.medium` EC2 host, an Elastic IP, encrypted 40 GB gp3 disk, private S3 storage and CloudWatch logs. The host serves the compiled React application, FastAPI with two processes, a background worker and the ClamAV definition updater. MongoDB Atlas database `shiftproof` remains the primary database; no production SQLite database is used. The unrelated food-rescue database, bucket and other AWS applications were not repurposed.

Host nginx terminates HTTPS and forwards to a loopback-only Docker web port. The internal API port is not published. Only TCP 80 and 443 are publicly allowed; administration uses AWS Systems Manager instead of SSH. The app stays online when the Mac sleeps or is switched off.

The user-owned Duck DNS name points to the stable AWS Elastic IP. It has its own browser-trusted Let's Encrypt certificate; HTTP redirects to HTTPS. Hosting and data remain on AWS and Atlas. No Duck DNS token is needed on the server because the Elastic IP is static. Keep the Duck DNS registration active and update its DNS record if that IP changes.

CloudFront refused creation because this AWS account requires service verification. The original IP address therefore also retains a trusted Let's Encrypt IP certificate. Certbot checks both certificates twice daily and gracefully reloads nginx after renewal. IP certificates last approximately six days, making the renewal timer essential. See [Let's Encrypt's IP certificate documentation](https://letsencrypt.org/2026/03/11/shorter-certs-certbot.html) and [Certbot's webroot guidance](https://eff-certbot.readthedocs.io/en/stable/using.html#webroot).

This is a modest single-host deployment, not a highly available cluster. Host replacement, maintenance or database/provider outages can interrupt service. There is no promise that the application cannot crash. Container restart policies, health checks, an unhealthy-service watchdog and EC2 system-failure recovery reduce recovery time.

## Cost and boundaries

The queried AWS on-demand price for `t3.medium` in Mumbai was $0.0448/hour, approximately $32.70 for 730 hours. Disk, the public IPv4 address, modest logs, S3 and traffic bring the expected starting spend to roughly **US$40–60/month**, excluding taxes, sustained burst CPU credits, significant traffic and external MongoDB/Gnani/Gemini/email usage. This is an estimate, not a spending cap. Existing unrelated AWS resources have separate costs.

## Secrets and account access

Provider, SMTP and database settings are stored in the SSM SecureString `/shiftproof/production/environment`. Deployment writes a mode-600 environment file on the encrypted host disk. Runtime AWS access uses an instance role; AWS root/access keys are not copied into containers, the frontend, source archives or Git.

The supplied AWS credentials belong to the root account and were pasted into chat. **Replace and revoke those exposed root access keys through the AWS account console, enable root MFA and use a restricted deployment identity.** This follows [AWS root-user guidance](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html). Also rotate database, mail and provider credentials previously pasted into chat. Update private `backend/.env` and redeploy after replacing those provider credentials. Do not put replacement secrets into chat, Git or command output. Revoking the old deployment key does not interrupt the instance role used by the running app.

Secrets are deliberately omitted from this document. The release tool reads only an allowlist from `backend/.env`, requires the `shiftproof` database, and refuses environment files or symlinks in source archives. The legacy repository-root `.env` is not its configuration source.

## Deploy an update

Run from the original repository, after reviewing and testing the checkout:

```sh
backend/.venv/bin/python deploy/aws/release.py --profile YOUR_DEPLOYMENT_PROFILE
```

The tool uploads a source release to the private bucket, updates the encrypted parameter and starts an SSM command. It prints a release ID and command ID; **starting the command does not mean deployment succeeded**. Its non-secret metadata is also stored in the ignored `.sites-runtime/aws-deployment.json`.

The public address is retained in `/shiftproof/production/public-url`, a non-secret SSM parameter. Normal releases reuse it instead of reverting to the infrastructure stack's numeric URL. `FRONTEND_URL` uses the named address for verification, invitation and recovery links. Both the named address and the original IP are accepted application origins. Browser sessions and local drafts belong to their original origin, so sign in again on the new address and finish any local-only drafts in the old tab.

Check completion using the returned identifiers:

```sh
aws ssm get-command-invocation --profile YOUR_DEPLOYMENT_PROFILE \
  --region ap-south-1 --instance-id INSTANCE_ID --command-id COMMAND_ID \
  --query '{status:Status,error:StandardErrorContent}'
```

The installer locks deployment against the health watchdog and builds both images before changing services. Changed schema/bootstrap code runs while the old API is serving; identical schema code skips redundant Atlas index operations. It then replaces containers and waits for health checks. A failed activation attempts to restore the previous containers. There can still be a brief API interruption during replacement. The `current` symlink changes only after successful activation. Database migrations are not automatically reversed; preserve backward compatibility.

The infrastructure source is `deploy/aws/stack.yaml`. Inspect a CloudFormation change set before infrastructure updates: changing instance user data or instance configuration can interrupt the host. Do not blindly replace the stack. The instance's disk and S3 bucket are retained on deletion to avoid accidental data loss; they must be accounted for when deliberately retiring the deployment.

For a deliberate application rollback, select a retained, previously healthy release whose schema is still compatible. Through SSM, hold the same deployment lock and start its images before moving the active symlink:

```sh
exec 9>/opt/shiftproof/health.lock
flock -w 900 9
rollback_release=/opt/shiftproof/releases/PREVIOUS_RELEASE_ID
docker compose --env-file "$rollback_release/.env.production" \
  --project-directory "$rollback_release" -f "$rollback_release/deploy/aws/compose.yaml" \
  up -d --no-deps --wait --wait-timeout 360 api worker web scanner-updates && \
  ln -sfn "$rollback_release" /opt/shiftproof/current
```

Keep the previous environment file private. If credentials were rotated, update that release's private configuration before rolling back. A rollback must not restore a revoked credential or undo newer database records.

## Set up or replace the public hostname

1. Register a hostname you control and point its A record to the stack's Elastic IP. Do not set an AAAA record unless the host is configured for IPv6.
2. Copy `deploy/aws/setup-domain.sh` to the host through S3/SSM. Run `bash setup-domain.sh HOSTNAME CONTACT_EMAIL ELASTIC_IP`. It validates DNS, obtains a separate certificate using the existing HTTP challenge directory, validates nginx, and reloads it. The original IP listener stays available. A configuration failure restores the prior domain configuration.
3. Release with `--public-url https://HOSTNAME`. Later releases can omit that flag. The release tool refuses a hostname that points to another IP or an address containing credentials, a port, a path or a query.
4. Check HTTPS, sign-in, authenticated API calls and `/opt/certbot/bin/certbot renew --cert-name shiftproof-domain --dry-run`. The existing renewal timer and hook cover both certificates.

This setup uses standard HTTP certificate validation and does not store the DNS account password or token. DNS ownership, AWS availability and certificate renewal are separate operational dependencies.

## Operations

Use an authorized SSM session or Run Command on the stack's instance. Never print `.env.production` or decrypted parameter values into command logs.

```sh
cd /opt/shiftproof/current
docker compose --env-file .env.production --project-directory . -f deploy/aws/compose.yaml ps
curl --fail http://127.0.0.1:8080/api/v1/health
systemctl list-timers 'shiftproof*'
df -h /
```

Application logs go to `/shiftproof/shiftproof-live` with 14-day retention. They exclude HTTP access logs, password bodies and provider tokens. The host has a two-minute health watchdog and a CPU alarm. Alarms currently have no email/SNS subscriber; review them in CloudWatch. The health endpoint proves database connectivity, not provider correctness. Its failed-job count includes historical failures and is not a count of current incidents. Retry relevant failed jobs through authorized UI controls instead of replaying every old email/job.

The `shiftproof-certificates.timer` checks twice daily. Validate renewal after network/proxy changes:

```sh
/opt/certbot/bin/certbot renew --dry-run
nginx -t
```

Keep previous releases for rollback, but monitor disk usage and remove obsolete release directories/images deliberately once no running container or rollback target depends on them. Never prune volumes or delete the active environment directory as general cleanup.

## Voice jobs and evidence

Production sets `JOB_NAMESPACE=aws`. Queued and processing records carry this namespace internally; API responses still expose `queued` and `processing`. Dedupe keys are namespaced too. This prevents a different machine connected to the same Atlas database from consuming an AWS speech job and storing its result on that machine's local disk. Keep development workers on a different namespace, and never run an old worker as the production worker.

Conversation creation and turns retry transient MongoDB write collisions with fresh authorization and the original idempotency key. A background speech job finishing while a worker answers must not discard that answer. Actual revision mismatches and revoked permissions still stop the operation; duplicate requests use the same namespaced job key and cannot append another turn.

Media is private under the bucket's `evidence/` prefix, with server-side encryption, blocked public access and versioning. Every download still goes through application authorization. Generated speech can be regenerated from its authorized source. Original worker recordings cannot be reconstructed from text.

During migration, **30 existing evidence files were available and copied with checksum verification; 10 retained audio records already had no source file on the Mac**. Existing local backup archives did not contain those originals. Their transcripts/report records remain, but the original audio is unavailable unless recovered from the machine that created it. The deployment does not manufacture replacement original recordings.

## Backups and restore

`shiftproof-backup.timer` creates a database snapshot daily around 21:00 UTC (02:30 IST), with up to five minutes of jitter. It uses an Atlas snapshot session so collections share a consistent read point without stopping the API. The BSON archive contains collection options, indexes, record counts and SHA-256 checksums; it is encrypted in S3 under `backups/` and expires after 30 days. S3 evidence versions are retained for 30 days after becoming noncurrent. Recover database and evidence to a compatible point in time.

Trigger an additional snapshot through SSM:

```sh
systemctl start shiftproof-backup.service
journalctl -u shiftproof-backup.service --no-pager -n 15
```

For restoration, download a selected archive privately and configure a **new empty** MongoDB database in an isolated process. Run `python -m app.mongo_backup restore /private/database.tar.gz` from the backend environment. The command refuses a nonempty database and validates all archive hashes before writing. Restore never targets the running `shiftproof` database. Verify counts, indexes and representative authorized records; then arrange a deliberate cutover. Recover matching S3 object versions separately. Delete only the isolated restore-test database after a drill.

## Refresh and crash protections

The AWS frontend is a compiled static build: no Vite hot reload and no uvicorn development reload process. Service-worker updates wait for existing tabs to finish instead of immediately replacing their cached release. An error boundary offers manual recovery when rendering or a lazy chunk fails, rather than leaving a blank screen or creating an automatic reload loop. Encrypted local drafts and existing confirmation/idempotency protections remain in place.

## Validation record

The initial deployment validation below was completed for release `20261109120736` on 9 November 2026. Subsequent address and copy checks are recorded after the table.

| Check | Result |
| --- | --- |
| Standard backend suite | 191 passed; six optional integration tests skipped in that run |
| Targeted media/security/voice checks | 17 passed, including real audio conversion and disguised-playlist rejection |
| Queue, speech recovery and conversation checks | 34 passed |
| Final conversation retry, media and voice checks | 38 passed, including duplicate turns, stale edits and revoked access during retries |
| Isolated MongoDB integration suite | Four passed |
| Real Gnani/Gemini synthetic conversations | Two passed, covering 100/85 and Hindi 75/80 scenarios |
| Public page checks | All 18 covered successfully; slow desktop matrices retried separately |
| Contradiction browser scenarios | All 42 covered successfully, including targeted retries on the connected production build |
| Workspace browser scenarios | All eight covered successfully; includes desktop/mobile layout matrices, offline shell, encrypted drafts, role workflows, navigation and dialogs |
| Dedicated voice browser scenarios on isolated MongoDB | All six passed together, including 100/85 confirmation and supervisor resolution, 75/80 scope clarification, microphone denial, stale results, offline answers and missing-playback recovery |
| Live AWS worker and supervisor | Login, pages, private speech playback and secure cookies passed; no browser application errors |
| Live AWS transcription | Audio upload, conversion, Gnani STT and expected transcript content passed |
| Draft stability | Unsent draft retained through polling with no document reload |
| Live media codecs | WebM, Ogg and M4A validated and converted to WAV |
| SMTP and PDF scanner | STARTTLS/login/NOOP and clean-PDF scan passed; no test email sent to another person |
| Full backup restore drill | All 55 collections verified by checksums in an isolated database, then the test database was deleted |
| Certificate renewal | Certbot staging renewal dry run passed |
| HTTP security boundaries | Unauthenticated workspace 401; hidden environment file 404; foreign-origin mutation 403 |
| Runtime IAM boundary | Own environment parameter readable; unrelated parameter access denied |
| S3 protection | Public access blocked, versioning enabled, encryption configured |
| Dependency/container audits | npm and Python dependency audits clean; final API and web Trivy scans report zero vulnerabilities |
| Host security updates | No pending security updates reported by the package manager |
| Small concurrent health check | 30 of 30 requests succeeded at five concurrent requests; p95 1.33 seconds; this is not a capacity benchmark |
| Production build | TypeScript and Vite build passed; existing chunk-size advisory remains |

The named address and copy update is deployed as release `20261109122639`. Its follow-up checks passed:

- Six release-address tests, including persistence, first-deploy fallback, permission failures, foreign DNS targets and invalid origins.
- 77 backend contradiction tests, plus a direct check that punctuation in original transcript identifiers still matches correctly.
- Five public browser checks and two workspace workflows covering report submission, supervisor verification, immediate alerts and handover receipts. The connected production build passed.
- Live worker and supervisor sign-in on `shiftproof.duckdns.org`, secure cookies, private S3 speech playback, audio upload and real Gnani transcription. The unsent draft stayed in place without a document reload, and neither role produced a browser application error.
- Trusted HTTPS and healthy API responses on both the hostname and original IP. The IP listener is explicitly the TLS default because IP clients may omit SNI. The named-origin request reached authentication; a foreign-origin mutation was rejected with HTTP 403.
- The running API uses the new address for `FRONTEND_URL`, while both URLs remain allowed origins. The saved public-address parameter matches the hostname. No verification email was sent to another person for this check.
- Certificate renewal dry run for the new hostname, active renewal timer and nginx configuration validation.
- Live desktop landing capture, the **Take a demo** link to signup, Hindi mobile signup, direct theme switching and no signup horizontal overflow. Updated captures are in the private local AWS review gallery.
- No literal or HTML/Unicode-escaped em dashes remain in tracked authored text. Missing values now use contextual English/Hindi labels. Original user reports, historical recordings and Git history were not rewritten.

Browser retries used the same workflow assertions against the compiled frontend with `/api/v1` configured. Initial runs encountered shared-machine delays, a SQLite fixture lock, and voice tests included without their separate fixture server. The workspace runner now excludes the dedicated voice suite; its count fixture supplies explicit units and its cache allowlist includes the external theme initializer. The dedicated voice suite supports isolated MongoDB and allows network time for its job chain. That run exposed a real concurrent-write error while answering a clarification; the transaction retry and namespaced duplicate lookup fixes were verified by all six voice scenarios passing together. No stale-edit or permission assertion was removed.

The scanner runs against the final runtime filesystem. Build installers and their caches are removed after dependency installation; there is no ignored-CVE allowlist. A passing scan is a time-specific result, not a guarantee of future security; maintain dependency and container updates. Atlas network-access rules and account-wide AWS MFA/billing configuration were not changed as part of this application deployment.

Local screenshots and browser results are in `artifacts/review/aws/index.html`. They may contain account information and are intentionally excluded from Git and deployment archives.

To repeat connected build and browser checks:

```sh
VITE_API_BASE_URL=/api/v1 npm run build
npm test
STORAGE_MODE=local S3_KEY_PREFIX='' npm run test:workspace
STORAGE_MODE=local S3_KEY_PREFIX='' npx playwright test --config playwright.dialogue.config.ts
```

The dialogue configuration supplies its own API, provider fixtures and frontend ports. Keep its test processes separate from production workers and from other sessions' test databases. Do not run browser fixtures against the live `shiftproof` database.

For MongoDB browser runs, provide `SHIFTPROOF_BROWSER_DATABASE_URL` privately with a fresh database named `shiftproof_test_browser_<unique suffix>`. The test server rejects other names and nonempty databases, and removes its database at shutdown. Allow longer assertion waits for an Atlas run than for local SQLite; keep the assertions and workflow coverage intact.

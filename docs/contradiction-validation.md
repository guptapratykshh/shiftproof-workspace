# Contradiction QA: 6 November 2026

The supplied five Hindi/Hinglish contradiction scenarios and the different-shift control were tested, with 36 additional scenarios in `fixtures/contradiction-cases.json`. The live sweep used Google Chrome and the running Python/MongoDB application, in a separate **ShiftProof Contradiction QA Lab** organization containing only synthetic data. Existing operational records were not used as fixtures.

## Results

| Check | Result |
| --- | --- |
| Live Chrome + MongoDB scenario sweep | **42/42 passed**, zero JavaScript page errors |
| Production-build Chrome acceptance suite | **42/42 passed**; all six supplied examples submitted through the UI; additional cases through authenticated API requests in Chrome contexts |
| Original production workspace and mail suite | **10/10 passed**, including offline/account isolation, task approval, safety alerts, handover receipts, responsive views, recording cancellation and optional spoken review |
| Public Chrome suite | **17/17 passed** across 320–2560px, English/Hindi and light/dark |
| MongoDB regression run in a separate disposable Atlas database | **88 passed** |
| Additional isolated MongoDB checks | **10 passed**, including six pairs of simultaneous submissions, timezone boundaries and extraction guards |
| Live Gemini extraction | **18/18 successful responses** on the final run; assertions passed for negation, uncertainty, different entities, historical updates, prompt injection and targets versus actual production |
| Final local backend regression | **131 passed, 4 Mongo-only tests skipped**; those Mongo-specific paths passed in the separate Atlas run |
| Production TypeScript/Vite build and whitespace check | Passed |

The Chrome conflict screens were checked at 320, 390, 768 and 1600px. They retain both original statements, their immutable source versions, structured facts, severity, a neutral clarification request and a supervisor verification recommendation. A supervisor resolution preserves the original evidence after reload. Workers cannot read another worker's source or resolve the conflict; another organization cannot access it.

The result table and five live evidence screenshots are available in [the QA gallery](../artifacts/contradictions/index.html).

## Findings fixed

- Separated quality, dispatch, machine availability and task completion instead of comparing arbitrary generic status strings.
- Added order/task identity, product, reporting period, observation time and total/additional counting basis to confirmed report fields and corrections.
- Normalized supported entity formatting, Unicode digits, translated batch/order labels, quantity units and bounded Hindi/Hinglish/English number words. Original transcripts remain unchanged.
- Kept different shifts, different dates, additional production, incompatible units, different entities/products and explicit changes over time out of the contradiction list. Pending inspection is treated as an incomplete update, not proof of rejection.
- Removed the 100-report candidate cutoff; batched version loading avoids one version query per candidate.
- Rechecked corrected source versions after a previous comparison was resolved. Old comparisons retain their original version links.
- Serialized comparison writes per department so simultaneous submissions do not each miss the other report.
- Prevented the AI from silently reducing an explicitly multi-entity update to one entity. It now preserves the original content and requests separate reports.
- Rejected invented quantities, entity/time/target numbers used as quantities, non-finite numbers and negative production counts. Large counts still detect a one-piece difference.
- Kept counterpart values and supervisor notes out of worker/unauthorized comparison lists.
- Added bounded retries for MongoDB sign-in and evidence-upload conflicts. Aborted sign-in cookies are discarded; failed asset inserts remove unreferenced private files.
- Included the new comparison facts in spoken review.
- Excluded runtime/build/test reports from the development file watcher, preventing QA artifact generation from resetting an in-progress live form.

## Real speech checks

The voice acceptance uses synthetic Hindi speech supplied to Chrome's fake microphone device, with the real MediaRecorder, upload endpoint, Gnani transcription, Gemini extraction and background worker. It does not mock provider responses. Both opposing recordings passed through the complete Chrome flow, including consent, recording, automatic transcription, extraction, human confirmation and submission. The original audio, original transcripts and AI suggestions were retained; the pair produced one quality-status conflict. Supported spoken identifiers and quantities were preserved (batch 204 and 50 pieces).

A separate real-provider test mixed the rejected-batch recording with synthetic pink noise; the transcript/extraction retained batch 204, quantity 50 and rejected status. A three-second silent recording returned an empty transcript. Both checks passed. The resulting voice conflict was verified as **critical**, real Gnani spoken review returned a 970,284-byte WAV, and supervisor resolution left both original sources unchanged. These are synthetic acoustic tests, not measurements of a real factory floor.

## Interpretation and limits

The first supplied spoken pair does **not** identify CNC-01 in both statements: Worker A says “CNC machine” and “aaj”; Worker B says CNC-01 without an explicit period. Its test metadata supplies the machine identity, product and common reporting context. The confirmed-field test passes; raw text alone correctly needs identity/period confirmation. The other four positive pairs and the different-shift negative control passed directly from the final live extraction outputs.

These are candidate contradictions for human verification, not automatic decisions about who is right. A recommended quality hold is a recommendation; no external warehouse or machine lock is implied. Unknown wording, omitted identity or timing, unsupported units and unsupported number words still require confirmation. The number-word normalizer is deliberately bounded, not a complete multilingual numeral parser.

Default comparison context is the same organization, department, reporting day and shift, within a 24-hour candidate window. An explicit matching dated reporting period can connect different submitting shifts. Distinct explicit observation times are kept separate. Without an explicit common observation time, status changes more than five minutes apart are treated as updates. This conservative heuristic should be tuned against real labeled handovers before relying on it operationally.

Clean/synthetic/noisy QA audio does not establish real factory microphone/acoustic accuracy. All checks are representative, not exhaustive load, multi-instance availability or independent security certification. Temporary provider errors occurred during exploration and were surfaced without losing the original update. Test-harness retries corrected selectors, session switching and login-rate-limit interactions; the final recorded sweeps passed.

The final service review found 12 retained failed jobs across the live database: 11 earlier scheduler attempts and one earlier extraction. They were left intact as history. The latest eight scheduler runs (09:30–09:37 UTC) all succeeded on their first attempt, and all nine processing jobs belonging to the synthetic QA organization succeeded. This confirms recovery at the time of review; it does not establish sustained scheduler reliability under heavier concurrent load.

The live URL uses the existing temporary Cloudflare tunnel and depends on the Mac and local services remaining available. This work did not deploy a separate static Sites frontend or create permanent hosting. QA credentials and raw live session state remain in ignored, private runtime files and are not included in this report.

## Integration with updated main

The changes were rebased without conflicts onto `54c1a63`, which includes the merged UI revamp (PR #1) and worker voice workflow (PR #2), on `feat/contradiction-qa-integration`.

Post-rebase validation passed: 131 backend tests (four Mongo-only skips), all 42 contradiction Chrome cases, all 17 public Chrome cases, and the production TypeScript/Vite build. The workspace/mail run passed nine cases and exposed one regression from the merged save-button behavior: initial handover publication was disabled until prefilled text was edited. Giving that action the explicit **Publish version** label preserves the save-change guard while allowing publication of an unchanged draft. The browser test now asserts that this button is enabled without editing; its production-build rerun passed, including separate handover and critical-item receipts. The earlier Atlas and real-provider results above were recorded before this rebase and were not repeated for this integration.

## Re-run

```sh
cd backend
.venv/bin/pytest -q
cd ..
npx playwright test --config playwright.contradictions.config.ts
SHIFTPROOF_BUILD_TEST=1 npm run test:workspace -- integration/workspace.spec.ts integration/mail.spec.ts
npm test
npm run build
```

The contradiction browser suite owns ports 8011/5185 and `/tmp/shiftproof-contradiction-qa`, separate from the original workspace suite. It uses a fixed production build so source edits do not reset forms during a test. Authenticated test sessions are reused instead of bypassing the application's sign-in rate limit. Live/provider tests are opt-in runtime scripts because they require configured credentials and write synthetic QA records.

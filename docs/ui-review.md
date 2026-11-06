# UI review — 6 November 2026

Changes are on `feat/ui-polish-light-default`, based on `main` at `9ea113f`. No PR was created, no branch was pushed, and `main` was not changed.

## Changes

- Light is the initial theme, including on a device using dark mode. Explicitly saved light/dark choices and the existing system-preference migration still work. The initial HTML and theme-color metadata also use light mode.
- Softer neutral page backgrounds, white cards/sidebar, quieter borders, consistent corner radii, and more readable landing-page text preserve the plum brand.
- Cards in adjacent columns keep their natural height. Short alerts and empty sections no longer stretch to match tall lists. Mobile column gaps no longer double up from card margins.
- Desktop navigation uses the page scroll instead of an independent scrolling sidebar. Links are grouped, and workers can directly reach reports, handovers, alerts and drafts.
- Mobile navigation fills the screen height, has a dismissible backdrop, contains keyboard focus, closes with Escape, restores focus, and prevents background scrolling. Its own scroll remains necessary for long menus.
- Task and workforce filters collapse on mobile, show how many filters are active, and retain entered values when closed. Desktop filters remain visible.
- Long dialogs keep the page behind them still. Their close control stays visible while scrolling; closing returns focus to the triggering control.
- Setup steps wrap into visible rows instead of requiring horizontal scrolling. Selected multi-select pills use a readable foreground in both themes.

## Coverage and results

The final visual sweep visited **75 route/role combinations**: 12 public/auth/error pages, 27 owner views, 23 supervisor views and 13 worker views. Each was captured at **1440px and 390px**. It included detail pages for tasks, reports, handovers, alerts, conflicts, departments, teams, workers and supervisors where the role allows access.

All **150 final screen checks** completed with zero JavaScript page errors, horizontal page overflow, clipped form controls, or visible nested page/card scrollers. Textareas, media controls, modal dialogs and the open mobile menu intentionally retain appropriate local scrolling. The two incomplete invitation-link states show their expected explanatory error messages.

An additional **48 captures** cover the nine organization setup steps, seven analytics tabs, task creation/templates, department creation, worker creation/import, handover creation, task board and task calendar, at desktop and mobile widths. None had horizontal overflow or clipped controls. Representative screenshots were visually inspected and refined; automated layout checks covered every listed page.

| Verification | Result |
| --- | --- |
| Public Chrome suite, English/Hindi and both themes, 320–2560px | 17 passed |
| Production workspace/mail suite, including offline drafts, voice controls, task verification, handover receipts, responsive roles and new mobile navigation/filter behavior | 11 passed |
| Final focused production rerun after dialog refinement: task verification, mobile navigation/filters, long-form scrolling and focus restoration | 3 passed, including one new dialog regression test |
| Core contradiction flows through Chrome, including resolution and source comparison | 6 passed |
| Final public rerun: 320/390px, default theme/persistence, keyboard interactions | 4 passed |
| Production TypeScript/Vite build and whitespace checks | Passed |

See the [before/after gallery](../artifacts/ui-review/index.html) and [complete route coverage](../artifacts/ui-review/coverage.json). Full visual-run screenshots remain in the ignored local `.sites-runtime/ui-review/` folder.

## Scope

Visual review used isolated SQLite test accounts with synthetic operational data. It did not modify real organization records. External speech/AI providers are disabled in that visual preview; this pass verifies their UI states and the existing browser voice tests, not new real-provider accuracy. Chrome viewport tests are not physical-device, Safari or Firefox certification.

The local visual preview is `http://127.0.0.1:5186` while its services are running. The normal application also uses this checkout, so a refresh picks up the branch's UI changes. Saved theme choices continue to take precedence over the new default.

## Repeat the checks

```sh
npm test
SHIFTPROOF_BUILD_TEST=1 npm run test:workspace -- integration/workspace.spec.ts integration/mail.spec.ts
npx playwright test --config playwright.contradictions.config.ts --grep 'TC-'
npm run build
```

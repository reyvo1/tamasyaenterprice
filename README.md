# TAMASYA Enterprise — operational UAT

Source baseline: RC2 build 20260929, packaged locally 2026-09-30. This public repository contains application source and synthetic test harness only; never commit private configuration or guest data.

## Status: UAT FULL BELUM SELESAI

895 local integration/artifact checks and 194 unit assertions passed before this repository was created. Those are historical RC2 evidence, **not proof that every button, role, domain or workflow has been browser-tested**. GitHub Actions runs fresh tests; only an actual completed run establishes its result.

`Operational UAT evidence` executes fresh core/Growth/currency/interproperty/HA and HQ/worker/report/storage/delivery suites, followed by browser desktop/mobile and Telegram simulator tests. MySQL data is disposable and isolated on localhost:23384. Current browser scenarios cover Growth/Enterprise module navigation and PR draft creation/reload, not every UI operation.

The coverage inventory deliberately preserves NOT_TESTED entries. Source discovery, page loads, tab clicks, HTTP 200, API regression and a successful job are not interchangeable with full operational acceptance. `artifacts/coverage-summary.md` documents the gap. No skip or absence of a failure is presented as a pass.

## Required operational matrix

For each menu/control, cover authorized and forbidden roles; normal, invalid and empty inputs; persisted result after reload; duplicate/retry and ambiguous response; cancel/reversal/audit; accounting, tax and stock invariants where relevant; offline/reconnect; desktop/mobile. Dynamic modal/table controls, flags and state-dependent buttons must be discovered in addition to static markup.

Domain map: `work/enterprise/api/domains/`. Coverage includes front office/reservation/check-in/out, finance/accounting/tax/bank/shift, POS/inventory/procurement, HR/attendance/payroll/employee service, housekeeping/maintenance, public website/guest service, configuration/security, Growth/Enterprise, multi-property/HQ/control plane, offline/cluster and communications. Domain/subdomain here includes functional modules; real DNS/subdomain routing also requires a target environment.

## Telegram

The owner explicitly requested simulator first and has no designated test bot/chat yet. Simulator tests exercise the real simulator API, identity binding, role spoof rejection and menu replies. **Live Telegram remains BLOCKED_LIVE.** Callback branching, role-specific operational mutations, webhook retries and all media/state paths still require explicit scenario evidence; they are not considered covered by `/menu`.

Do not put tokens in chat or source. A future live job must use a protected GitHub Environment with secrets for a dedicated test bot/chat, explicit manual dispatch and approval. Do not target guest/staff operational groups.

## Running / evidence

Push to `main` or dispatch the workflow manually. CI installs PHP 8.5, runner MySQL, Node 22, Python dependencies and Chromium. The source fixture harness predates CI and is being verified on the runner; failure is a real blocker, not an accepted result. Desktop/mobile means two Chromium viewports, not Safari/Firefox coverage.

Only `artifacts/` is uploaded, for 14 days. Raw fixture logs, dumps, credentials, sessions, private keys and browser network traces are excluded; traces can contain tokens. Dependencies/actions are pinned. No production deployment is performed.

Before accepting full UAT, reconcile the inventory against behavioral evidence and get operator sign-off. Production HA/DR/PITR, real devices/provider IAM, DNS/TLS and representative FPM load cannot be proven by local simulation alone.

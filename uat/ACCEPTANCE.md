# Full operational acceptance — required evidence

The owner requested every menu, domain/subdomain, button and Telegram path. That remains the target, not a completed claim. Do not rename partial CI success to full UAT success.

## Evidence levels

- INVENTORIED: control/route discovered; no behavior proven.
- NAVIGATION_VERIFIED: clicked and expected panel visible; not a mutation test.
- API_VERIFIED: request/state invariants proved; not a browser click test.
- BEHAVIOR_VERIFIED: identified UI control, preconditions, actual interaction, business outcome and persisted reload verified.
- BLOCKED_LIVE: real external service/physical device unavailable; simulator cannot close it.
- OPERATOR_ACCEPTED: hotel operator validates suitability; not supplied by a generated test script.

## Each behavioral scenario must state

1. Domain/subdomain, page/control and valid role(s), feature flags and starting DB state.
2. Valid/invalid/empty/boundary input and permission denial cases.
3. Expected business state, financial/tax/stock changes and audit evidence, with explicit assertions.
4. Cancel, duplicate, retry, timeout/uncertain and offline/reconnect outcomes where supported.
5. Reload and independent persisted-state check; rollback/reversal via official workflow.
6. Desktop/mobile coverage and remaining browser/device gaps.

## Current gaps (must remain visible)

The generated static inventory is a lower-bound discovery tool, not an exhaustive state graph. Dynamic menus, modals, data-dependent table buttons and role/flag-specific controls require runtime enumeration. Existing API suites prove many business invariants, but are not credited as UI behavior tests. Browser authentication currently uses the real login API plus session setup; interactive login/2FA/password recovery is not yet covered. PR browser tests cover draft/submit/approve, not downstream receiving/payment. Telegram menu/callback/role tests do not cover all operational mutations, media, webhook retry and live transport.

All ten HTML entrypoints, PHP admin tools, public web forms, compiled React routes, POS, staff workflows, HQ and every dynamic control must receive reviewed scenario mapping before acceptance. DNS subdomains, HTTPS routing and production deployment remain environment-specific tests.

## Safety

Fixtures must be synthetic, disposable, isolated and incapable of sending messages/payments to live recipients. Never weaken assertions to make CI green, count skipped/disabled tests as passing, or replay ambiguous mutations with a new operation ID. Raw traces/logs/session dumps are private and must not be uploaded to this public repository.

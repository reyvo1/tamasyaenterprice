# Findings from CI expansion

This repository is post-RC2 development. The packaged local RC2 ZIP is retained unchanged; its historical report does not certify subsequent commits. Each change below needs fresh CI evidence.

## Fixture timestamp reads on UTC hosts

The SQL assertion helper inherited server timezone while the API explicitly used `APP_TIMEZONE`. Comparing a TIMESTAMP read by the helper against the property's local date failed on the UTC runner. The helper now sets the same timezone offset as the property. Assertions were retained, not weakened.

## Standalone mirror timestamp interpretation

The standalone mirror configured PHP timezone but did not configure its PDO session timezone. Canonical snapshots emitted in property time could consequently be written into TIMESTAMP columns under the host's UTC session, causing checksum mismatch. The agent now sets the property's offset on every iteration, including daemon/DST transitions. A dedicated absolute-timestamp comparison supplements the full-dataset checksum guard. Verification remains tied to the actual CI run, not this explanation.

## Fixture transport interruption

A subsequent run failed on a connection error after HQ v3 and before provider bridge assertions. The cause is not yet established. New public diagnostic artifacts report only code locations and categorized error counts; private raw logs, tokens and payloads remain excluded. No retry of a mutation with a fresh operation ID is introduced to hide this failure.

A disjoint-port local reproduction found the TLS fixture refusing to bind with EADDRINUSE, despite no listening server during preflight. The previous test listener range overlapped Linux ephemeral client ports, permitting TIME_WAIT collisions. Fixture listeners have moved below the usual ephemeral range (DB 23384, HTTP 281xx/282xx); local verification uses a separate offset. This addresses the reproduced bind failure, not proof that every earlier transport failure had the same cause.

## Consent gates voucher issuance

`tamasyaEnterpriseIssueVoucher()` requires an active `loyalty_program` consent and
refuses to issue without one, but no browser scenario exercised the CRM panel, so
that cross-control rule had no UI evidence at all. The new CRM scenario asserts it
in both directions: issuance is refused before consent exists and refused again
after revocation, while the same call succeeds while the consent is active. The
refusal must leave the voucher list empty and must not mutate the loyalty balance.

## One active session per staff and device

`issueSessionTokens()` revokes every existing session for the same staff AND
device before issuing a new one. The first CRM scenario logged in a second time
from the suite's `X-Device-ID: uat-browser`, which silently invalidated the token
`beforeEach` had just placed in `sessionStorage`; the page then received
`401 Unauthorized` on its first CRM call. The application behaved correctly — one
live session per device is intended. The scenario now seeds its guest
precondition from inside the page with the token the suite already holds. Any
future scenario that needs its own credentials must use a distinct `X-Device-ID`
rather than a second login on the shared one.

## Mobile PO approval is still timing out intermittently

Run 36736174277 failed the procurement scenario on the **mobile** project with a
timeout while tapping Submit/Approve, even though 36722254327 passed the identical
code two hours earlier. The scenario runs before the CRM one in file order, so the
CRM change cannot have caused it; this is pre-existing flakiness in the mobile
approval path, not a regression from that commit. The scenario is left as it is —
no retry, timeout bump or assertion was weakened to hide it — and the failure is
recorded here until a run proves it stable across repeated runs.

## Mobile tap() hangs on CRM guest selection, cause still unproven

Runs 36737342387 and 36738107357 both failed the CRM scenario on the **mobile**
project only, at the `tap()` on the "Pilih" control; desktop passed the same
scenario in full. The recorded diagnostics rule out the obvious causes — the
control was visible, enabled, unobstructed by the loading overlay, scrolled to the
centre, and `document.elementFromPoint` at the tap point returned the BUTTON
itself. So the element is neither hidden nor covered, yet the touch never lands
within 15s.

The suite already records the same intermittent shape on the procurement mobile
approval buttons, and most other scenarios drive their mobile controls with a
plain `click()` and pass. Whether this is touch-emulation flakiness under
`isMobile`/`hasTouch` or genuine movement in the layout is **not yet established**;
the scenario now records the first and settled bounding boxes plus a `boxStable`
flag so the next run distinguishes the two. No timeout was raised, no retry was
added and no assertion was weakened to make this pass.

## Acceptance gap

Current browser and Telegram scenarios cover only part of the requested operational surface. See `ACCEPTANCE.md` and generated coverage inventory. Source inventory counts are not passing-test counts. Telegram live remains unavailable by the owner's explicit simulator-first choice.

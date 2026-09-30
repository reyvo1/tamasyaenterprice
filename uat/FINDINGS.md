# Findings from CI expansion

This repository is post-RC2 development. The packaged local RC2 ZIP is retained unchanged; its historical report does not certify subsequent commits. Each change below needs fresh CI evidence.

## Fixture timestamp reads on UTC hosts

The SQL assertion helper inherited server timezone while the API explicitly used `APP_TIMEZONE`. Comparing a TIMESTAMP read by the helper against the property's local date failed on the UTC runner. The helper now sets the same timezone offset as the property. Assertions were retained, not weakened.

## Standalone mirror timestamp interpretation

The standalone mirror configured PHP timezone but did not configure its PDO session timezone. Canonical snapshots emitted in property time could consequently be written into TIMESTAMP columns under the host's UTC session, causing checksum mismatch. The agent now sets the property's offset on every iteration, including daemon/DST transitions. A dedicated absolute-timestamp comparison supplements the full-dataset checksum guard. Verification remains tied to the actual CI run, not this explanation.

## Fixture transport interruption

A subsequent run failed on a connection error after HQ v3 and before provider bridge assertions. The cause is not yet established. New public diagnostic artifacts report only code locations and categorized error counts; private raw logs, tokens and payloads remain excluded. No retry of a mutation with a fresh operation ID is introduced to hide this failure.

A disjoint-port local reproduction found the TLS fixture refusing to bind with EADDRINUSE, despite no listening server during preflight. The previous test listener range overlapped Linux ephemeral client ports, permitting TIME_WAIT collisions. Fixture listeners have moved below the usual ephemeral range (DB 23384, HTTP 281xx/282xx); local verification uses a separate offset. This addresses the reproduced bind failure, not proof that every earlier transport failure had the same cause.

## Acceptance gap

Current browser and Telegram scenarios cover only part of the requested operational surface. See `ACCEPTANCE.md` and generated coverage inventory. Source inventory counts are not passing-test counts. Telegram live remains unavailable by the owner's explicit simulator-first choice.

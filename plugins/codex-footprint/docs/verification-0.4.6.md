# Version 0.4.6 review follow-ups — 2026-10-24

## Scope and outcome

The six remaining review findings are addressed for the personal macOS plugin. The work does not add Linux CI or promise Linux runtime acceptance. The running personal 0.4.5 worker/configuration and user data were not changed; this is the 0.4.6 PR candidate.

| Finding | Result and validation |
| --- | --- |
| Cooled urgent walker occupies the reservation | A due lifecycle-active project can reclaim the least-progressed non-active cursor. The old cursor closes before the new one opens, retaining the descriptor cap and last complete baseline; its unfinished walk restarts later. A real worker/CLI/hook fixture waits the actual 60-second hot window, then finishes the next project in 2.63s with 8 cursors while the old large trees remain pending. This is a fixture result, not a universal latency promise. |
| Native-only acceptance on a polling host | FSEvents cases explicitly skip off macOS or with forced polling. The production fixture uses a declared two-second polling refresh and verifies external-write growth. Both native macOS and forced-polling macOS paths pass. Skips have reasons and are counted separately from passes/failures. |
| chmod denial under root | The permission-denial fixture explicitly skips before creating the fixture when effective UID is zero. The actual non-root macOS denial case passes. The root branch was statically checked; no privileged/root or Linux execution was performed. |
| Historical partial coverage uses today's inventory | A daily gap ledger stores the failed attempt against its own measurement day. CLI acceptance verifies today's failure does not contaminate yesterday, yesterday's failure remains visible after today's success, and pruning rolling observations does not erase the saved gap. Gaps have the same 90-day retention as daily records. A partial gap prevents a full-day coverage claim. |
| ZIP omits browser driver | The package allowlist includes `.mjs`; a real CLI-generated ZIP contains a byte-identical `tests/e2e_dashboard_browser.mjs`. Node syntax validation passes. |
| A failed attempt makes an old complete endpoint look fresh | Status ages the complete endpoint and exposes `latest_attempt_at` separately. CLI acceptance confirms the root is simultaneously partial and stale, with the old complete timestamp preserved. |

The previously fixed baseline-migration interruption finding remains covered by the runtime-recovery suite. Its completion receipt commits with the recovered complete baselines; a missing receipt triggers recovery again.

## Validation evidence

New black-box CLI/worker cases were written before runtime changes. The initial run had **0 passes and 6 failures**. During validation, an artificially slowed scheduling fixture was corrected to use the production 0.2-second cadence, and the polling baseline gate was corrected to check retained completed endpoints rather than demand all current inventory rows be complete at the same instant. Child failure details are retained in reports. Failures were investigated rather than ignored.

The final marketplace harness installs the actual candidate in an isolated Codex profile, compares runtime and acceptance-script hashes, and runs **99 cases: 99 passed, 0 failed**. Breakdown: 20 legacy, 15 global, 14 edges, 9 dashboard/service, 8 event/history/hook, 3 capacity, 6 scope, 10 reliability, 6 review follow-ups, 5 runtime recovery and 3 safe-upgrade cases. The forced-polling skip is an explicitly verified subcase, not a native-acceptance pass. The initial source HEAD in the machine report is the preceding commit; hashes identify the tested candidate.

Environment: macOS, native arm64 Python 3.12.14, effective UID 501, existing compatible Codex CLI, local temporary profiles/state and loopback. No model calls, credentials, actual desktop notifications or personal service changes. Full regression was selected because scheduler admission and persisted daily metadata changed. No unit tests were added.

Replay from the WXY repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/system-temporary-directory/footprint-review
PYTHONDONTWRITEBYTECODE=1 python3 plugins/codex-footprint/tests/e2e_monitor_reliability.py --event-backend polling --output /absolute/system-temporary-directory/polling.json
node --check plugins/codex-footprint/tests/e2e_dashboard_browser.mjs
```

Fixture inputs and commands are recorded in the reports and test source. Process files, temporary databases, ZIPs and disposable profiles are removed after recording reports; no test artifacts enter Git. Only the verification report is committed.

## Acceptance boundaries

This verifies the requested macOS behavior and package contents. It does not verify Linux, privileged permission-denial behavior, multi-day uptime or idle power. UI interaction did not change, so visual browser acceptance was not repeated. Preempted unfinished walks restart and may repeat metadata reads; there is no persistent per-file checkpoint or unlimited active-project capacity. Historical partial attempts already lost before this ledger existed cannot be reconstructed. No new scans or cleanup of personal storage were performed.

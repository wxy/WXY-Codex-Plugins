# Version 0.4.3 review regression acceptance — 2026-10-10

The five code-review findings on [PR #2](https://github.com/wxy/WXY-Codex-Plugins/pull/2) were confirmed. The [failure-mode plan](review-0.4.3-plan.md) and CLI/MCP test cases were written before runtime changes. All six new cases failed against 0.4.2 for the named behavior (not environment/setup errors), then passed after correction.

| Finding | Correction and replay evidence |
| --- | --- |
| P1: missing external paths inherit the system disk on Linux | Missing `/Volumes` mounts are rejected on every platform. Absent historical paths without a selected anchor/configured-root association stay unclassified; explicitly pinned offline mounts keep their identity. CLI branch simulation excludes stale inventory/alerts/capacity from the system series. |
| P2: report/explain/cleanup responses expose unselected records | Project background roots/volumes before filtering, sorting and limits. Three CLI and three MCP responses agree; retained outside inventory is not deleted. Explicit historical-analysis results keep their independently requested scope. |
| P2: projected daily full-day coverage is stale | Recompute from the closed report day, displayed complete windows and remaining selected pending endpoints. Outside-only gaps disappear; selected incomplete/pending roots, partial days, empty scopes and missing window metadata remain incomplete. Saved report payloads are unchanged by reads. |
| P2: skipped alerts are recorded as emitted | Keep a bounded scope-specific scan cursor separate from explicit emission IDs. A selected-volume/mount-availability change restarts scanning but preserves actual emission evidence. Mixed/outside-only batches, legacy empty-ID watermarks, scope switching and progress beyond 100 excluded findings are verified. Existing concurrent/opt-out/ack regressions pass. |
| P2: pending metrics stop at 100 | Count all retained selected unacknowledged rows independently of the recent detail list. Fixture: 130 internal findings, 10 acknowledged, 20 outside; details show 100 and the internal pending metric correctly shows 120. |

## Replay and actual results

From the WXY repository root, using Python 3.14.6, macOS, a compatible Codex CLI, a writable system temporary directory and local subprocess/loopback support:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 plugins/codex-footprint/tests/e2e_review_scope.py --output /absolute/report-directory/review
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/report-directory/installed
```

Installed-copy outcome: **78 passed, 0 failed**: 20 legacy, 15 global, 14 edges, 9 dashboard/service, 8 event/history/hook, 3 dual-disk capacity, 6 review regressions, 3 safe-upgrade. The actual WXY 0.4.3 entry is installed into a disposable profile, source/cache runtime hashes match, and an unconfigured install remains inactive. The report's initial HEAD is the pre-fix commit because tests ran on uncommitted changes; the hashed runtime files identify the tested contents. Only replay reports remain; temporary profiles, metadata databases, bootstrap files and subprocess artifacts are removed.

Inputs are generated per case under a system temporary directory: configuration/workspace, seeded volume/inventory/alert/daily metadata, newline-delimited MCP requests and real trusted-hook subprocesses. No personal artifact scan, history reconstruction, OS notification, model call or deletion runs in these suites.

The Linux-specific regression bootstraps the real CLI with `sys.platform="linux"` on macOS. It verifies the previously faulty platform branch and shared response chain, not native Linux mount/filesystem acceptance. Native Linux testing remains a separate platform gate. No visual HTML changes were made; 0.4.2's browser-layout acceptance remains documented separately. OS/Codex-visible notification delivery is not inferred from hook emission.

Legacy notice receipts preserve only concrete last-batch IDs, so older alerts without explicit emission evidence may be offered once again. The old watermark cannot truthfully prove they were sent. Future receipts distinguish actual submissions from skipped records; acknowledgement is unchanged.

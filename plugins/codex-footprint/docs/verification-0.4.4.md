# Version 0.4.4 monitoring reliability acceptance — 2026-10-16

## Reproduced failures and resulting behavior

Black-box CLI/worker cases were written before their corresponding runtime fixes. The initial six-case run on 0.4.3 had five behavior failures and one pass: production scheduling exceeded the fixture deadline, a pruned/partial endpoint destroyed growth comparison, rollover hid an available cross-day baseline, stale successes were not exposed, and permission gaps lacked a coverage label. Scope-change safety already passed. Later tests reproduced a newly active project blocked by eight busy roots and a closed historical day incorrectly labeled overdue; each failed before correction.

| Path | Verified result |
| --- | --- |
| Production budgets | 61 disposable roots, one containing 5,000 files, complete their first endpoints in 1.32 seconds in the source run. A separate writer produces a growth alert within the 20-second acceptance window. The shared 20-ms slice and 2-second idle/capacity interval are preserved; pending work uses a 0.2-second pause. |
| Busy-root admission | Eight deliberately slowed 200-file trees remain pending when a real CLI lifecycle event activates another project. Its endpoint completes in 3.35 seconds in the source run. One walker slot is reserved for lifecycle-active projects; existing cold cursors continue. |
| Native hints | 160 coalesced real filesystem writes trigger a growth finding without a new observation of an unrelated quiet root. Genuine native loss/mount/root flags retain conservative invalidation; existing native/fallback suites pass. |
| Durable baselines | A complete endpoint survives observation-history pruning and an intervening incomplete row. A subsequent complete measurement reports the external writer's exact 65,536-byte increase. |
| Day rollover | A legacy store migrates retained complete metadata. A 32,768-byte cross-day increase is labeled cross-day; same-day growth stays unknown. |
| Coverage | Stale complete records, permission failures and scope changes remain distinct. Closed historical reports retain their recorded window coverage instead of becoming currently overdue. |

## Replay

From the WXY repository root, with Python 3.14.6, compatible Codex CLI, macOS FSEvents, a writable system temporary directory and local subprocess/loopback support:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 plugins/codex-footprint/tests/e2e_monitor_reliability.py --output /absolute/reports/reliability.json
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/reports/installed
```

The final marketplace harness installs the actual 0.4.4 candidate into a disposable profile and compares source/cache runtime hashes. **87 passed, 0 failed**: 20 legacy, 15 global, 14 edges, 9 dashboard/service, 8 native/history/hook, 3 capacity, 6 prior review regressions, 9 reliability and 3 safe-upgrade cases. An unconfigured installation remains inactive. The final personal installed copy independently passes all nine reliability cases. The tested runtime hashes identify the uncommitted candidate; the harness's initial HEAD is the preceding mainline commit.

Optional read-only browser acceptance requires Node.js 22+ and Google Chrome at its standard macOS application path, a running local panel at port 8766, two selected disks and retained reports containing stale/cross-day evidence:

```sh
node plugins/codex-footprint/tests/e2e_dashboard_browser.mjs /absolute/reports/browser.json
```

Actual Node.js 26.7.0 / headless Chrome run at 390 × 844: two disk columns, no document overflow, no script exceptions, project rows and explicit stale/cross-day/unknown labels. The actual endpoint, not injected browser data, supplies the records. This verifies rendering separately from the Codex in-app browser; native browser automation could not initialize because the workspace root includes a symlink.

Only reports remain. Disposable installation profiles, test trees, metadata databases and browser profiles are removed; no screenshots, full logs or test databases are committed.

## Personal service and remaining boundaries

The existing personal installation was upgraded through `scripts/update_plugin.py`, preserving old cached hook entrypoints and the existing stable runtime/service configuration. The service runs 0.4.4 with healthy FSEvents; the inspected candidate run reports zero global event-loss rescans. Saved marketplace selection and other plugins are unchanged. The pre-existing daily reminder keeps its time and purpose; it now falls back to the stable CLI when a running chat still holds old MCP code, detected by the missing coverage fields. A fresh chat loads the installed MCP implementation.

A real metadata-only daily report now has 30 same-day comparable roots and 20 explicitly cross-day comparisons; 11 roots lack a complete endpoint for that day. These are endpoint intervals, not full-day or full-disk coverage. Pending large trees are still catching up after restart; protected paths remain genuine gaps. No destructive action was performed.

The 61-root fixture timing is not a production latency promise. Large metadata trees, concurrent development, filesystem latency and machine load affect completion. A pre-final candidate's live catch-up sample used about 155 CPU seconds over 943 wall seconds (about 16% of one core); the sampling report identified an x86-64 Python running under Rosetta. This is not an idle-power measurement or proof of lower whole-machine CPU. Traversal slices exclude scheduling/SQLite/filesystem overhead. The patch fixes avoidable global invalidation, unfair admission and baseline loss; it does not implement a persistent per-file delta cache, transient-peak capture or verified process ownership.

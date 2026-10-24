# Version 0.4.5 runtime recovery acceptance — 2026-10-22

## Problem and result

The personal service still ran a detached 0.4.3 worker despite an earlier 0.4.4 candidate deployment. Its singleton lock prevented the new supervisor from taking over, and the stable CLI pointed into a cache directory that had been removed. A pre-existing baseline table also lagged newer complete retained observations. These were deployment and persistence failures, not proof that elapsed installation time guarantees comparable measurements.

0.4.5 pins the service resources in a fingerprinted private state snapshot, stages before switching the stable pointer, and verifies an old worker's recorded PID, command and open state-lock file before retiring it. Upgrade reloads the matching existing login service. It does not install an unsolicited service or enable disabled observation. A one-time reconciliation recovers newer complete endpoints even when the baseline table already exists. Partial and changed-scope measurements still cannot supply growth.

Retained file counts prioritize known small roots among equally pending cold work; active projects retain their reserved admission and large-tree cursors continue. Explicitly configured macOS VM metadata is attributed to the internal disk despite its separate APFS volume. No swap-file contents are read. Migrated Codex data requires its explicit target root; no arbitrary symlink traversal was added.

## Failure-first and installed validation

Black-box CLI/worker fixtures preceded the corresponding runtime fixes. The original four recovery cases failed before implementation. A later VM admission case failed before the APFS exception, and the small-root case timed out before the admission-order change. No unit tests were added.

| Acceptance path | Result |
| --- | --- |
| Existing stale baseline table | Newer retained complete inventory restored; subsequent external write reports exactly 65,536 bytes. |
| Cache eviction | Stable CLI remains executable after the source cache is renamed away; preparing the runtime does not start monitoring. |
| Version handoff | New supervisor retires an isolated old-version worker holding this state's lock and becomes the current worker. |
| PID protection | An unrelated process holding the lock survives the refused handoff. |
| VM scope | Native macOS VM path admitted by the CLI with zero snapshots; this fixture does not scan real swap files. |
| Small-root backlog | A known one-file root refreshes while eight deliberately slowed large roots remain pending. |
| Existing reliability | 61-root production-budget, active admission, native event, pruning, rollover, stale/permission and scope-change cases pass. |

Final marketplace harness: **93 passed, 0 failed** — 20 legacy, 15 global, 14 edges, 9 dashboard/service, 8 event/history/hook, 3 capacity, 6 scope, 10 reliability, 5 runtime recovery and 3 safe-upgrade cases. The harness installed the actual candidate in a disposable Codex profile and compared source/cache runtime hashes. An unconfigured installation remained inactive. Two fixture issues encountered during validation were corrected: canonical `/var` versus `/private/var` comparison and polling two changing rows instead of one consistent row. The final full run passed after these corrections; no product failure was ignored.

Replay from the WXY repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/system-temporary-directory/footprint-validation
```

Environment: macOS, native arm64 Python 3.12.14, compatible Codex CLI, local subprocesses/filesystems, FSEvents and loopback. Fixtures use temporary profiles/state, no credentials, model calls, personal login-service changes or desktop notifications. Keep the resulting report and remove process artifacts after recording it. Source/cache hashes identify the tested working candidate; the initial HEAD recorded by the harness is the preceding commit.

## Personal deployment and boundaries

The existing enabled login service was explicitly reinstalled with native arm64 Python. The stable runtime now points outside the plugin cache; the live worker reports 0.4.5, a healthy FSEvents backend and no last error. The existing loopback dashboard responds with the new worker and read-only data. The migrated external Codex root completed two measurements and produced a comparable growth interval; the VM metadata root completed its first measurement. No local migration backup or user data was deleted.

At the checkpoint, complete roots since final restart rose from 25 to 41, and stale roots fell from the initial 46 to 12. Today's retained summary has 51 same-day and 10 explicitly cross-day comparable roots. These are observed endpoint intervals, not full-day or full-disk coverage. Large pending trees continue to catch up. Protected cache paths and paths without readable complete endpoints remain genuine gaps; the repair does not grant macOS permissions or manufacture missing history. The current chat's MCP process may retain older code, so personal acceptance used the pinned stable CLI and the actual dashboard HTTP response.

This acceptance does not prove multi-day uptime, idle power, exact physical-block accounting on APFS, transient-peak capture or process ownership. No UI interaction changed in 0.4.5, so browser visual checks were not repeated; 0.4.4's recorded UI evidence remains separate. No repeated whole-disk analysis, automatic deletion or cloud service was introduced.

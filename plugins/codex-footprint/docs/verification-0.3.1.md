# Version 0.3.1 acceptance report — 2026-10-08

## Replay and environment

From the WXY repository root:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output /tmp/footprint-v031-report
```

Environment: macOS 26.6.2, Python 3.14.6, Codex CLI 0.162.0-alpha.2, Unix local filesystem and loopback listeners. The runner installs the real local marketplace entry in a disposable profile, compares runtime hashes, runs four installed-copy E2E suites and real-CLI safe-upgrade acceptance. No model, credentials, personal state changes, native notification or login-service installation is used by these fixtures. Reports are retained; generated files, profiles, databases and subprocesses are removed.

Inputs: checked-in fixture recipes generate external writes, concurrent hooks, historical references, eight roots with 2,500 one-byte files, 200 empty roots, HTTP probes, a version-0.2.0 upgrade, missing entrypoints, crashing startup and unrelated-plugin sentinels. The fairness fixture fixes a 1,000-entry/200-ms budget independently of production settings. The CPU case runs eight real worker ticks at 20-ms pause; its one-second child CPU limit is a local regression check, not a whole-machine guarantee.

## Actual results

| Suite | Passed | Failed |
| --- | ---: | ---: |
| installed_core_results | 19 | 0 |
| e2e_global | 15 | 0 |
| e2e_global_edges | 14 | 0 |
| e2e_monitor_dashboard | 9 | 0 |
| safe_upgrade | 3 | 0 |

All 60 passed. Source and installed runtime fingerprints matched. Unconfigured installation did not create observer state. Upgrade preserved unrelated plugin/configuration and recreated old-chat entrypoints before returning. Missing cached scripts and crashing startup did not block hook completion.

Before the scheduling optimization, the 200-root CPU fixture consumed 26.50 CPU seconds and failed; the optimized source consumed 0.64 seconds in the first green run. Production traversal defaults are a 2-second tick, 5,000-entry maximum and 20-ms traversal slice. Scheduling, SQLite, blocked filesystem calls and hook process startup are outside the slice; do not interpret it as a total CPU ceiling.

The first full release run exposed a fairness fixture coupled to the former 50-ms default: only 2,152/2,500 entries completed in six ticks at the new 20-ms default. Fixing the test's explicit budget separates fairness from wall-clock throughput; it still detects unused budget in the old scheduler. The final installed-copy suite passed.

## Personal CPU investigation, separate from fixtures

A 10-second cumulative-process-CPU comparison measured the old observer at 4.47 percent of one core, StorageManagementService at 68.60 percent and ApplicationsStorageExtension at 57.28 percent. Stopping only the observer did not immediately lower the system services (76.10 and 59.61 percent in the following short window). Hooks and the panel remained active, so this was not a complete plugin-off experiment.

After the user closed macOS Storage settings, CPU dropped. At 18:40:16 +0800 the system log recorded client PID 5092 disconnecting, StorageManagementService exiting after its last connection, and ApplicationsStorageExtension tearing down its context. Subsequent process checks found both service PIDs absent while the Footprint panel remained running. This links ongoing service lifetime to its settings-page client. It does not identify why the system statistics became expensive or exclude a prior indirect effect from plugin activity, cleanup or filesystem changes. The observer source does not call StorageManagement APIs; it uses filesystem metadata and statvfs.

The restored runtime's CPU, actual service recovery and scheduled-chat receipt are documented in the task delivery report. A short closed-page comparison cannot establish plugin overhead while that page is open. Actual logout/login and first 21:00 reminder remain separate user-visible acceptance gates.

## Runtime fingerprints

- `src/codex_footprint/monitor.py`: `79510bfb5cd30aa28b10ff02478f18fe603ea7898c999012e0e6d26fe7dd6874`
- `hooks/hooks.json`: `3504e5760f0b23d0b21a78e2895a27795d84715a2e2a5baac1d6898f0b3b7bcf`
- `scripts/update_plugin.py`: `0109275baae22631410da8fa3bd48b5a39b0c3a009248ad970abb738130dc5f7`
- `tests/e2e_monitor_dashboard.py`: `d5adfcaa707ba49ddcf37cca128f5347a24092830bfe1a227d464cd5f18b5cb0`

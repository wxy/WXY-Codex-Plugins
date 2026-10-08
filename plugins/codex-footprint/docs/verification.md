# Verification and replay — 0.4.0

## Test-first black-box suites

Prerequisites: macOS/Linux, Python >=3.9, writable system temporary directory, subprocesses, hardlinks and sparse files. No credentials/model/network/third-party packages. Run from the plugin directory:

```sh
python3 tests/e2e.py --output artifacts/legacy
python3 tests/e2e_global.py --output artifacts/global
python3 tests/e2e_global_edges.py --output artifacts/edges
python3 tests/e2e_monitor_dashboard.py --output artifacts/dashboard
python3 tests/e2e_event_monitor.py --output artifacts/events  # macOS only for native cases
```

Each suite retains reports only with commands, environment/prerequisites, generated-input recipes, outcomes and necessary diagnostics. Full process/transport logs are not retained. Temporary fixtures are removed; checked-in runners recreate them. Fixtures use lower thresholds and real external writer processes, not synthetic byte counters. No native notifications run in fixture suites.

The 19 legacy cases cover snapshots/accounting, hook transport, seven-tool MCP handshake, input rejection, non-destructive plans, budgets, missing roots, concurrency, privacy, retention and reproducible relocated archives. The 15 global cases cover stable state, concurrent sessions/projects, fair sliced progress, external growth, alert silence/re-alert/ack, missing endpoints, worker lock/health, explicit pre-enable archived evidence and inode deduplication, new MCP history operation and monitoring-off analysis. The edge suite covers stable defaults, legacy DB preservation, root aliases, symlinks, invalid config fail-open, exclusions, bounded partial history, worker crash recovery, long tool polling, host disable, a separate notification probe, scope-change baselines real explicit refresh and full bounded budget use with many roots.

New behavior scenarios are written/run failing before corresponding runtime changes. Existing legacy tests are preserved. Optional existing unit regressions are supplementary and are not real-host acceptance.

## Installed-copy test

From WXY repository root, with a compatible Codex CLI available:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output test-artifacts/codex-footprint/marketplace
```

Creates/removes a disposable Codex profile, installs the actual WXY entry, compares source hashes, confirms unconfigured installation stays inactive and runs all five suites from its installed cache. Reports include CLI version/commands/install receipt/source HEAD. No personal settings, hook trust or model calls are changed.

## Real Desktop acceptance

1. Install from WXY, review/trust hooks and enable shared global observation. Record source/cache hashes, host version and actual config/state paths.
2. In actual chats from different projects, collect real host lifecycle IDs and verify they reach the common inventory. Synthetic fixture events cannot substitute for these.
3. Allow a baseline to finish. Request an external-tool artifact and inspect complete comparable endpoints, growth, alert evidence and overlapping session limitations. Never attribute whole-volume changes exclusively to the task.
4. Verify a meaningful notification is actually visible. `test-notification` is a labeled delivery probe, not a production growth finding; command acceptance is insufficient proof of visibility. Retain the result and method in the report; remove test screenshots/AX process files after recording acceptance.
5. Query status/report/alerts/explain/review plan. Confirm no cleanup executed. Explicitly request historical analysis only when wanted; pre-enable fixture coverage is distinct from investigation of the user's whole history.
6. Disable and confirm background work stops; re-enable preserves state. Record real first-baseline completion and overhead rather than extrapolating fixture timings.

Save JSON/Markdown receipts with commands, prerequisites, input artifact metadata, expected/actual outcomes, actual event evidence, notification outcome and open gates. Report missing host/visibility evidence candidly. Cross-chat/user-visible acceptance may remain partial even when all automated suites pass.

## Package

```sh
python3 scripts/codex_footprint.py package --profile local --output dist
```

Identical source produces identical archive hashes. Full runtime/hooks/MCP/tests/docs ship. No official-marketplace publication is part of acceptance.

## Version 0.3 acceptance

The new black-box suite was run failing before implementation. It covers budget reuse, an actual external writer and autonomous worker alert, metadata-only/idempotent daily rollups, endpoint retention under pruning, fixed-route read-only panel and request rejection, new MCP annotations/date rejection, recovery-service preview and successful disabled supervisor exit. Tests bind temporary loopback ports and remove all fixtures/processes. A service plan is not proof of actual login/restart: install on the personal host, record the elected PID, terminate only that worker, and verify a different elected PID/healthy heartbeat plus preserved SQLite history. A real logout/login remains a distinct manual gate.

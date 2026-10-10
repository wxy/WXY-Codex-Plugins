# Global configuration — 0.4.3

Enable once per machine, independently of chats/projects. Missing configuration means inactive hooks. Historical investigation can still run on explicit request while monitoring is off.

## Enable, inspect, stop

From the installed plugin directory:

```sh
python3 scripts/codex_footprint.py enable
python3 scripts/codex_footprint.py status
python3 scripts/codex_footprint.py alerts
python3 scripts/codex_footprint.py disable
```

Default discovery covers existing Codex state, immediate `~/develop` directories and known caches/tool directories (`Library/Developer`, `Library/Caches`, `.cache`, `.npm`, `.gradle`, `.cargo`, Homebrew Cellar). Trusted lifecycle workspace paths extend this scope. This is declared local development coverage, not recursive full-home/full-disk coverage or proof all cached bytes belong to Codex. Background observation selects the primary system/data volume and, when discovery is enabled, the volume containing `~/develop` (including a parent symlink to an external development disk). Other removable volumes are excluded even if a lifecycle event mentions them. Capacity is sampled independently for each selected disk; this does not traverse the whole disk. Explicit historical analysis retains its separate requested scope.

Advanced bounded setup:

```sh
python3 scripts/codex_footprint.py enable --root /absolute/development/path --no-defaults
```

`--root` may repeat; `--no-start` leaves automatic worker startup off for controlled runs; explicit `scan` still requests refresh. `--notifications inbox` suppresses desktop commands and retains local findings. `tick --rounds 100` is a bounded one-shot runner for fixtures. `test-notification` sends an explicitly labeled acceptance probe without fabricating a growth finding.

## Shared paths and migration

State resolves from `CODEX_FOOTPRINT_DATA`, else `${XDG_STATE_HOME:-~/.local/state}/codex-footprint`. **`PLUGIN_DATA` is ignored**, because the host may vary it by plugin version. Configuration uses `CODEX_FOOTPRINT_CONFIG`, else `config.json` in shared state. `CODEX_HOME` locates local session evidence and global host plugin settings. Overrides must be shared by all clients.

`enable` creates version 2. If a version-1 config exists, it is saved as `config.json.v1-backup`; original `footprint.sqlite3` remains intact. New monitoring uses `global.sqlite3`. `init-config` remains a legacy version-1 entrypoint; its bounded synchronous capture engine and `$CWD` support are retained for compatibility. Query the old database by explicitly pointing `CODEX_FOOTPRINT_CONFIG` at the backup. If an old installation used per-version `PLUGIN_DATA`, point `CODEX_FOOTPRINT_DATA` at that known state before migrating; no guessed directories are moved automatically.

## Version-2 settings

See the disabled `config/example.json`. Roots are absolute/`~` paths; nested paths compact to avoid overlapping traversal. Root/home and canonical aliases, final symlinks and state descendants are rejected/excluded. Child symlinks and cross-device boundaries are skipped. Unknown settings fail validation. Exact basename `exclude_names` apply across walks. New exclusions establish new comparable baselines.

| Setting | Default | Meaning |
| --- | --- | --- |
| `enabled` | false in example | Global observation switch |
| `discovery` | true | Known development roots plus event workspaces |
| `monitor.interval_seconds` | 2 | Tick pause |
| `monitor.refresh_seconds` | 60 | Polling pause; native dirty-root debounce uses at most 2 seconds |
| `monitor.event_backend` | auto | Public macOS FSEvents when available, otherwise polling; `polling` opts out |
| `monitor.reconcile_seconds` | 1,800 | Native quiet-root reconciliation interval |
| `monitor.slice_entries` | 5,000 | Per-tick shared entry budget, reused while time remains |
| `monitor.slice_seconds` | 0.02 | Metadata traversal time slice |
| `monitor.autostart` | true | Restart worker on trusted hook |
| `monitor.development_volume` | null | Auto-select the `~/develop` volume when discovery is on; an absolute mount path pins a second disk, e.g. `/Volumes/MacSSD`. The system volume is always selected. An unplugged selected disk remains visible with stale/missing coverage. |
| `notifications.codex_context` | true | Nonblocking warning/context on the next active trusted chat hook |
| `notifications.backend` | desktop | macOS notification adapter or inbox |
| `notifications.cooldown_seconds` | 3,600 | Minimum re-alert delay |
| `notifications.material_growth_bytes` | 256 MiB | Material additional occupancy for re-alert |
| `notifications.minimum_free_bytes` | 10 GiB | Unattributed capacity-pressure threshold |
| `thresholds.large_bytes` | 1 GiB | Crossing large-occupancy threshold |
| `thresholds.growth_bytes` | 256 MiB | Complete-endpoint increase |
| `thresholds.rapid_bytes_per_second` | 64 MiB/s | Average endpoint growth rate, not peak throughput |
| `thresholds.many_files` | 10,000 | New file entries in an interval |
| `thresholds.sustained_intervals` | 3 | Consecutive positive complete intervals |
| `history.max_files/max_records` | 2,000 / 100,000 | Historical source budgets |
| `history.max_seconds/max_entries` | 10 / 100,000 | Shared parse/measurement budgets |
| `retention.max_snapshots` | 500 | Global finished observations/samples/findings/results per table |
| `retention.max_events` | 5,000 | Global retained event limit |

Legacy `observer` options apply only to version-1 snapshots; version-2 scheduling uses `monitor`. A large first baseline may take multiple ticks. Incomplete roots expose progress/errors and unknown growth. Running walks resume across ticks; restart begins unfinished walks again. Whole-volume capacity changes are not Codex-attributed growth.

Run `install-service` explicitly on macOS to install `~/Library/LaunchAgents/xingyu.wang.codexfootprint.plist` and a stable `state/runtime` link to this plugin. It runs as your user, starts at login and restarts unexpected exits with a 10-second throttle. `service-plan` previews without changes; `remove-service` removes only that service and preserves history. After disabling and re-enabling, run `install-service` again to reload the service. Without a service, workers start on enable/trusted hooks/explicit scan. Existing explicit monitor settings are preserved on upgrade; adjust them intentionally to adopt the new defaults. Global disable (or WXY host plugin global toggle off) stops the worker without erasing history. No per-chat setting changes are needed.

## Panel and daily summary

The elected worker serves `http://127.0.0.1:8766/`; `dashboard` returns its URL and retained state. `CODEX_FOOTPRINT_PANEL_PORT` can override the port. `panel --port PORT` starts a standalone read-only server, without starting observation. A port conflict does not stop monitoring; unavailable panel status is explicit. Only fixed GET routes are accepted; no arbitrary files or write endpoints are exposed. Local applications can read the endpoint; there is no remote binding or account.

`daily-report [--day YYYY-MM-DD]` updates one idempotent daily report from monitor metadata only, including while observation is disabled. Daily first/last complete endpoints survive short snapshot retention for 90 days. Unknown/changed-scope endpoints cannot produce growth. Dates with no records remain empty. The worker prepares today's report at/after 21:00 local time. Configure a separate Codex daily scheduled chat at 21:00 to refresh and report it through Codex Activity; this is not a whole-disk scan. Computer/app availability affects scheduled delivery; there is no promise of delivery while asleep.

Native mode schedules first baselines, dirty roots and low-frequency reconciliation; it does not repeatedly walk quiet roots on each chat operation. Polling fallback retains hot-project priority and a two-second minimum refresh pause; cold roots retain the configured pause. A root still needs a complete walk and comparable baseline. Neither the tick pause nor panel refresh is a guaranteed anomaly-detection deadline.

The panel defaults to 24 hours and supports 1 hour/7 days. Capacity history is stored by volume and minute for seven days independently of `retention.max_snapshots` (100,000-row safety cap). Each disk has its own available-space, observed-root, pending-alert and daily-report metrics. The x-axis always spans the selected range with time/date labels, and the y-axis has GB ticks. Minute history is matched by canonical mount path and retained aliases across device-ID changes after reboot/remount. Chart points preserve bucket extrema; gaps over five minutes and unrecorded edges remain blank. The delta describes only the actual first/last sample interval. Older missing history cannot be backfilled. Old daily root records without explicit volume attribution are not assigned a per-disk summary date based on paths that may have moved. Existing metadata is retained rather than deleted when scope narrows.

`notifications.codex_context=false` disables chat hook notices independently of the OS adapter. Notices use supported `systemMessage`/`additionalContext` outputs and continue the current operation. They are globally deduplicated and do not acknowledge findings. Completely idle chats cannot receive a hook until another operation; OS notifications and the separate 21:00 scheduled summary supplement this boundary.

Background `report`, `explain` and `cleanup-plan` responses share the selected-volume projection with status/panel/alerts. The latest explicit historical-analysis result remains a separate saved investigation and keeps its requested scope. Per-disk pending counts include all retained unacknowledged findings; recent details remain capped at 100. Daily coverage is recalculated after projection from selected endpoints, pending selected roots and a closed report-day window.

Hook notices examine at most 100 retained unacknowledged records and submit at most three selected findings per operation. A scope/volume-availability change resets only the scan cursor. Actual emission IDs stay globally deduplicated and bounded to 20,000 (the supported retained-alert maximum); scanning/skipping an alert is never delivery evidence or acknowledgement. Legacy receipts import their concrete last-batch IDs only, not the old watermark. Older emissions without explicit ID evidence may be offered once again; visibility remains unverified.

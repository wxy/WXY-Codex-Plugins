# Global configuration — 0.2.0

Enable once per machine, independently of chats/projects. Missing configuration means inactive hooks. Historical investigation can still run on explicit request while monitoring is off.

## Enable, inspect, stop

From the installed plugin directory:

```sh
python3 scripts/codex_footprint.py enable
python3 scripts/codex_footprint.py status
python3 scripts/codex_footprint.py alerts
python3 scripts/codex_footprint.py disable
```

Default discovery covers existing Codex state, immediate `~/develop` directories and known caches/tool directories (`Library/Developer`, `Library/Caches`, `.cache`, `.npm`, `.gradle`, `.cargo`, Homebrew Cellar). Trusted lifecycle workspace paths extend this scope. This is declared local development coverage, not recursive full-home/full-disk coverage or proof all cached bytes belong to Codex. Primary data-volume capacity and discovered-root filesystems are sampled separately.

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
| `monitor.refresh_seconds` | 60 | Minimum pause between completed root walks |
| `monitor.slice_entries` | 1,000 | Per-tick allocation split among roots |
| `monitor.slice_seconds` | 0.05 | Metadata traversal time slice |
| `monitor.autostart` | true | Restart worker on trusted hook |
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

No login agent is installed. Workers start on enable/trusted hooks/explicit scan; crash recovery waits for the next such action. Global disable (or WXY host plugin global toggle off) stops the worker without erasing history. No per-chat setting changes are needed.

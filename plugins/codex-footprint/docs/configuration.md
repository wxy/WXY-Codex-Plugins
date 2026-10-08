# Configuration

The target product uses one machine-wide configuration and shared history for all local Codex sessions. Roots are global discovery/scope settings, not per-chat setup. Global post-enable monitoring and explicitly requested pre-enable historical analysis are separate operations; see [product scope](product-scope.md).

The instructions below describe **0.1.0's existing explicit-root configuration**, not automatic global discovery or a background monitor. Those capabilities and shared worker/MCP/Hook path resolution still require implementation. Enabling this config does not activate alerts or reconstruct older sessions.

No configuration means hooks are inactive. The disabled example in `config/example.json` shows optional macOS development roots; none is enabled implicitly.

## Paths and initialization

`CODEX_FOOTPRINT_DATA` overrides `PLUGIN_DATA`, which overrides `${XDG_STATE_HOME:-~/.local/state}/codex-footprint`. Configuration comes from `CODEX_FOOTPRINT_CONFIG` or `config.json` in that state directory. Set a stable data/config path shared by hook and MCP execution environments; otherwise hooks may use a host-provided plugin data directory while MCP uses the fallback and appear to have different histories.

```sh
export CODEX_FOOTPRINT_DATA="$HOME/.local/state/codex-footprint"
export CODEX_FOOTPRINT_CONFIG="$CODEX_FOOTPRINT_DATA/config.json"
python3 scripts/codex_footprint.py init-config --root /absolute/path/to/project
```

This command opts into the specified scope and refuses to overwrite an existing file. Review/edit JSON to add Xcode DerivedData, CoreSimulator or another known development root. Disjoint roots only; overlapping roots and duplicate IDs are rejected. Whole-disk and whole-home roots are rejected. Existing root symlinks are rejected; symlinks within roots are skipped. The observer does not enter another filesystem device.

`$CWD` may be used as the entire root path. It resolves to hook `cwd`, CLI `--workspace` or the CLI process directory. MCP runs in the plugin directory; pass the intended absolute `workspace` when using `$CWD`. Static absolute roots are the simplest V1 setup. Root paths also support `~`. Unknown settings are rejected to avoid silently ignoring misspelled budgets.

## Budgets, signals, retention

| Field | Default | Meaning |
| --- | --- | --- |
| `observer.max_entries` | 100,000 | Total entries across all roots, maximum 200,000 |
| `observer.max_seconds` | 2 | Shared traversal budget, maximum 5 seconds |
| `observer.bucket_depth` | 1 | Directory aggregation depth, 1–3 |
| `observer.top_files` | 20 | Top files retained per root, 1–100 |
| `thresholds.large_bytes` | 1 GiB | Large allocated occupancy |
| `thresholds.growth_bytes` | 256 MiB | Growth from the selected baseline |
| `thresholds.rapid_bytes_per_second` | 64 MiB/s | Baseline-to-latest average, not peak write throughput |
| `thresholds.many_files` | 10,000 | File-entry count per directory bucket |
| `thresholds.sustained_intervals` | 3 | Positive complete observation intervals; unchanged intervals do not count |
| `retention.max_snapshots` | 500 | Retained snapshots globally, 2–2,000 |
| `retention.max_events` | 5,000 | Retained events globally, 2–20,000; at least max_snapshots |
| `exclude_names` | `[]` | Exact file/directory basenames to skip everywhere |

Settings that affect traversal change the scope identity. Queries after a scope change show no previous comparable history until a new baseline is collected. Missing or unreadable roots, budget exhaustion, too-deep directories and cross-device skips make coverage incomplete. Explicit exclusions and symlink skips are scope boundaries rather than scan errors. The observer's own state is always excluded.

Retained snapshots keep their corresponding events. Capture/pruning is transactional. Retention does not preserve an unlimited historical ledger or daily rollups, and shrinking retention may discard task baselines. Such tasks report unknown growth rather than silently substituting a different event.

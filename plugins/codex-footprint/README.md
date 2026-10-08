# Codex Footprint

**Development Storage Growth Monitor for Codex.** Independent developer plugin by Xingyu Wang; not affiliated with or endorsed by OpenAI.

Enable once to monitor supported local Codex sessions across projects. Ask explicitly to investigate surviving storage associated with older sessions, including artifacts from before installation. Prioritize large occupancy, substantial/rapid growth, many files and sustained accumulation. Default: **observe → explain → recommend**, with no deletion API or cleanup execution.

> 启用一次，全局观察本机 Codex 会话相关的开发存储增长；用户明确要求时，调查旧会话相关的现存占用，包括安装前的产物。抓大放小，只观察、解释和建议，不主动删除。

## Version 0.3.0

The local runtime includes a shared observer, automatic development-root discovery, volume-capacity samples, persisted alerts, explicit historical analysis, daily summaries and a local read-only panel. Nine MCP tools expose results in Codex. Version 0.3 improves fair scan scheduling and prioritizes recently active projects; an explicitly installed macOS user service provides login/crash recovery.

> 全局后台监控项目增长；全盘与历史分析只手动触发。新增只读面板、每日 21:00 监控汇总，以及可选的 macOS 登录与故障恢复服务。

Automated E2E verifies filesystem behavior and installed-copy operation. Actual host hook delivery, visible notifications and large-machine overhead require separate personal acceptance; native notification command success alone does not prove visibility. See [acceptance boundary](docs/v1-scope.md).

## Install and enable once

Requires macOS or Linux and Python >=3.9, with no third-party runtime packages. Desktop notifications currently support macOS only. Windows and remote/cloud workers are outside coverage.

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
codex plugin add codex-footprint@wxy-codex-plugins
```

Skip marketplace registration if already present. In Codex, review/trust the seven lifecycle hooks. Then run from the installed plugin directory:

```sh
python3 scripts/codex_footprint.py enable
python3 scripts/codex_footprint.py install-service  # macOS login/crash recovery, explicit operation
python3 scripts/codex_footprint.py status
```

This creates one global configuration and starts one detached observer. Defaults discover existing Codex state, immediate `~/develop` projects and known development caches; trusted hook workspace paths extend discovery. Whole-volume free space is sampled separately. No per-chat root setup or routine whole-home/disk traversal is required. Installation alone leaves observation inactive.

> 安装后允许 Hooks，再执行一次全局启用。配置和历史库跨会话、项目及插件版本共用。无需逐会话配置观察目录；目录覆盖与无法读取的区域会显示在状态中。全盘容量与开发产物占用分别统计。

State defaults to `~/.local/state/codex-footprint` (or XDG state location). `PLUGIN_DATA` is deliberately ignored so Hooks and MCP share state. Explicit global path overrides remain supported; see [configuration](docs/configuration.md).

## Where to see results

Ask “打开 Codex Footprint 面板” to open its localhost URL inside Codex. The panel refreshes retained data every 15 seconds and shows measurement age, coverage, projects, alerts, daily summaries and the latest manual historical result. It has no scan, delete or settings action.

> 后台运行时可在 Codex 浏览器面板打开 `http://127.0.0.1:8766/`。面板刷新不等于目录刚完成测量。

In a fresh Codex chat after upgrading, ask:

- “检查 Codex Footprint 状态” — worker health, roots, progress, volumes and coverage.
- “查看开发存储提醒” — meaningful findings and delivery outcomes.
- “分析已有 Codex 会话占用了多少空间，包括安装插件前的产物” — explicit historical investigation.
- “解释这个目录的存储增长，并生成处理建议” — retained evidence and a non-executing review plan.

> 提醒会尝试通过 macOS 通知送达，也保存在插件提醒记录中；系统设置可能阻止通知展示。正在运行的旧聊天可能仍使用旧 MCP，升级后新建聊天以加载新工具。

At 21:00 local time the running worker prepares a daily rollup from retained monitoring metadata. Configure one daily Codex scheduled chat to call `footprint_daily_summary`, report coverage and open/link the panel; that chat supplies the Codex reminder. It requires Codex and the computer to be running. No arbitrary background third-party Codex notification-center API has been verified; immediate anomalies retain the system adapter and inbox. See [notification boundary and schedule](docs/monitor-dashboard-plan.md).

Historical investigation is never an automatic effect of enablement or a normal report query. It currently reads supported local current/archived JSONL session records, extracts structured path evidence and measures surviving paths under budgets. Workspace association is a candidate, not proof of creation. Missing/unsupported/budget-limited sources remain explicit; absent historical measurements mean unknown pre-enable growth.

## MCP tools

| Tool | Behavior |
| --- | --- |
| `footprint_daily_summary` | Persist daily rollup from retained metadata only; no scanning/history reconstruction |
| `footprint_dashboard` | Read panel data and local browser URL |
| `footprint_status` | Read shared configuration, worker health and coverage |
| `footprint_scan` | Queue a bounded background refresh; does not block for a full scan |
| `footprint_report` | Read current inventory, retained growth and latest explicit historical result |
| `footprint_explain` | Explain retained evidence for a reported root or top file |
| `footprint_cleanup_plan` | Owner-tool review plan, no execution/reclaim promise |
| `footprint_alerts` | Read findings; optionally acknowledge an ID or all |
| `footprint_analyze_history` | Explicit bounded investigation; writes a derived local result |

The historical, daily-summary and acknowledgement operations are write-annotated. Read-only queries do not initialize missing state. `workspace`/`turn_id` arguments remain for version-1 compatibility; global mode supports session association filtering, not exclusive per-turn byte attribution. MCP never accepts arbitrary scan roots. Run `python3 scripts/codex_footprint.py serve` for local stdio transport.

## Measurement limits

- File blocks (`st_blocks × 512`), logical sizes and volume free space are separate quantities. APFS clones/compression/snapshots prevent exact reclaim estimates.
- Lifecycle windows are temporal/path associations, not verified process write ownership. Concurrent sessions and unrelated tools can contribute.
- Background walks read metadata only, skip symlinks/cross-device traversal and exclude their own state. Fair slices resume in the running worker; a restart begins unfinished walks again. Traversal is live rather than an atomic snapshot.
- Incomplete measurements are lower bounds with unknown growth. First discovery and scope changes establish a baseline. Root totals are **not additive** across shared hardlinks/time windows; explicit historical analysis deduplicates inodes globally.
- Workers start on enablement/trusted hooks. An explicitly installed macOS user LaunchAgent restarts failures and starts at login; without it, recovery waits for the next trusted hook or explicit enable/scan. Transient files between samples, Docker guest internals, unknown historical formats and full process provenance remain gaps.

## Verify and package

```sh
python3 tests/e2e.py --output artifacts/legacy
python3 tests/e2e_global.py --output artifacts/global
python3 tests/e2e_global_edges.py --output artifacts/edges
python3 tests/e2e_monitor_dashboard.py --output artifacts/dashboard
python3 scripts/codex_footprint.py package --profile local --output dist
```

Every E2E suite retains reports only, with commands, generated-input recipes, prerequisites and actual results. Temporary fixtures and processes are removed; full logs and databases are not archived. No credentials/model calls are required. [Verification](docs/verification.md) separates fixtures from actual Desktop acceptance.

Read [product scope](docs/product-scope.md), [implementation plan](docs/implementation-plan.md), [architecture](docs/architecture.md), [configuration](docs/configuration.md), [distribution](docs/distribution.md), and [privacy](PRIVACY.md).

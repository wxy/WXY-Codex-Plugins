# Codex Footprint

**Development Storage Growth Monitor for Codex.** An independent developer plugin by Xingyu Wang, not affiliated with or endorsed by OpenAI.

Codex Footprint observes development storage before and after Codex lifecycle/tool events, retains historical baselines, and surfaces heavy hitters: large occupancy, rapid or substantial growth, many files, and sustained accumulation. It defaults to **observe → explain → recommend**. It has no deletion API and never runs cleanup commands.

> 面向 Codex 的开发存储增长监测插件。记录任务窗口内的存储变化，抓大放小，解释历史大头并生成处理建议。不是 Cleaner，不主动删除。

## Status and local-use goal

Version 0.1.0 is a **local V1 skeleton with a working end-to-end observation flow**, intended for personal use in Codex Desktop. It preserves automatic lifecycle observation and local MCP. Automated transport E2E and isolated Codex package installation have passed; a real Desktop session's hook trust/delivery and overhead remain to be accepted.

Official-marketplace publication is outside the current scope. The earlier platform assessment is preserved only as [historical context](docs/history/2026-10-08-marketplace-assessment.md). See [local distribution](docs/distribution.md) for packaging and installation.

## Run locally

Requires macOS or Linux, Python 3.9+, local filesystem access, and no third-party runtime packages. macOS is the first target. Windows observer support is not implemented. The direct script works without installing a package:

```sh
python3 scripts/codex_footprint.py --version
python3 scripts/codex_footprint.py init-config --root /absolute/development/workspace
python3 scripts/codex_footprint.py scan
# Run a build or another development task.
python3 scripts/codex_footprint.py scan
python3 scripts/codex_footprint.py report
python3 scripts/codex_footprint.py cleanup-plan
```

`init-config` creates an opt-in configuration and refuses to overwrite an existing one. It does not install hooks or modify Codex settings. No configuration means no hook scanning and no state creation. Select narrow development roots rather than your entire home directory or disk. See [configuration](docs/configuration.md).

A first scan identifies existing occupancy and historical heavy hitters. It cannot reconstruct growth or ownership before installation. Growth uses the first retained baseline in the same scope, or the task's lifecycle baseline when a task is selected. `--session-id ID --turn-id ID` selects a turn; a turn requires a session. Incomplete endpoints produce unknown growth, never a zero-growth success claim.

## Install from WXY Codex Plugins

Maintained in `WXY-Codex-Plugins/plugins/codex-footprint/`. The earlier independent repository is retained as an initial history snapshot; see [migration provenance](docs/migration.md).

> 统一在 WXY Codex Plugins 中维护。原独立仓库保留为初始版本记录；之后的功能修改请在本仓库完成。


Review `.codex-plugin/plugin.json`, `.mcp.json` and `hooks/hooks.json` before installation. All hook handlers run the packaged Python entrypoint; they produce no stdout, never block the original operation, and do not change tool arguments or permissions.

Use a stable state location for both transports. For example, set these in the environment used to launch Codex (and configure MCP environment forwarding as appropriate):

```sh
export CODEX_FOOTPRINT_DATA="$HOME/.local/state/codex-footprint"
export CODEX_FOOTPRINT_CONFIG="$CODEX_FOOTPRINT_DATA/config.json"
```

The normal installation source is the WXY Codex Plugins marketplace. Add it if it is not already registered, then install only Codex Footprint:

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
codex plugin add codex-footprint@wxy-codex-plugins
```

> 从 WXY Codex Plugins 市场安装 `codex-footprint`，然后新建 Codex 会话、审查并信任 Hooks，再配置希望观察的开发目录。安装插件本身不会开启全盘扫描。

Open a new Codex chat, review and trust the installed hook definitions in the host's hook review UI, and check `footprint_status`. Installation alone does not grant hook trust. Neither install nor trust is performed automatically by this repository. Actual host lifecycle delivery remains a separate acceptance gate; see [verification](docs/verification.md).

## MCP tools

| Tool | Behavior |
| --- | --- |
| `footprint_status` | Configuration, history counts, integrity and supported capabilities |
| `footprint_scan` | New bounded snapshot of configured roots; metadata write only |
| `footprint_report` | Historical heavy hitters and optional session/turn growth |
| `footprint_explain` | Explain a reported directory from retained evidence |
| `footprint_cleanup_plan` | Owner-tool review plan; no execution or reclaim promise |

All tools accept optional absolute `workspace`, needed when roots use `$CWD`. Report/explain/plan accept `session_id`, `turn_id` and `limit` (1–100). Explain also accepts `path`. MCP never accepts arbitrary scan roots; roots come from the opt-in configuration. Queries read retained state; only `footprint_scan` creates observations. Start the local stdio server with `python3 scripts/codex_footprint.py serve`.

## Where to see results

V1 returns results in the Codex conversation through its five MCP tools; it has no dedicated panel or notification UI. In a new chat with the plugin loaded, ask: "Check Codex Footprint status", "Show historical storage heavy hitters", or "Explain storage growth for this task". First check that the observer is enabled, its configured roots are correct and a baseline exists. No configuration means inactive observation, and no previous snapshot means earlier growth is unknown.

> V1 的效果显示在 Codex 对话里，没有单独面板或提醒。加载插件后可说：“检查 Codex Footprint 状态”“查看开发存储历史大头”“解释这次任务的空间增长”。先确认已配置观察目录并产生基线；没有配置时不会记录，首次快照也无法还原此前增长。

The CLI `status`, `scan`, `report`, `explain` and `cleanup-plan` operations are also available for direct inspection. Use a stable shared state directory so hooks and MCP query the same history.

## What measurements mean

- File blocks (`st_blocks × 512`) are distinct from logical file sizes and whole-volume free space. Sparse files and hardlinks are accounted for; APFS clones, compression, shared extents and snapshots prevent an exact physical reclaim estimate.
- Hook windows support **temporal correlation**, not verified process-level write attribution. Other writers, concurrent Codex tasks, daemons and background descendants can contribute. Tool windows may overlap and must not be added together.
- Scans read metadata only, skip symlinks and cross-device traversal, exclude the observer's own state, and stop at entry/time budgets. A traversal is not an atomic filesystem snapshot. Unreadable/missing/budget-limited roots remain visible as incomplete coverage.
- V1 aggregates directory buckets and retains a bounded top-file list. It does not continuously sample during a long tool invocation, track peaks created and deleted between hooks, inspect Docker guest disks, or monitor the entire machine.

## Verification and packages

```sh
python3 tests/e2e.py --output artifacts/e2e
python3 scripts/codex_footprint.py package --profile local --output dist
```

The E2E runner executes the real hook commands, creates real files through an external subprocess, exchanges real MCP messages, and writes `report.json`, `report.md` and `transcript.json`. It needs no model call or credentials and cleans its temporary fixture directory. See [verification](docs/verification.md) for exact coverage and the distinction from real Codex Desktop acceptance.

Local ZIPs include complete hooks, MCP wiring, the observer core, docs and tests. They preserve relative paths and use reproducible archive metadata; `package --output dist` is equivalent to the explicit local profile.

Read [architecture](docs/architecture.md), [configuration](docs/configuration.md), [local distribution](docs/distribution.md), [V1 scope](docs/v1-scope.md), and [privacy](PRIVACY.md).

# Product scope — global monitoring and historical analysis

Confirmed product direction: **2026-10-08**. This is the target contract; the implementation boundary is recorded separately in [V1 scope](v1-scope.md).

Codex Footprint is an independent local developer plugin for Codex. It has two core functions: global monitoring after enablement, with meaningful alerts; and explicitly requested analysis of existing Codex-related storage, including artifacts that predate enablement. It defaults to observe, explain and recommend, with no deletion or cleanup execution.

> 两项核心能力：启用后全局监测所有本机 Codex 会话及其外部工具相关的空间增长，在值得关注时提醒；用户明确要求时，分析已有 Codex 会话相关的现存占用，包括插件启用前留下的产物。

## 1. Global monitoring after enablement

Enable once for the machine. All supported local Codex sessions contribute to one shared observer and history, across chats, projects and session restarts. Session and tool IDs are association labels, not observation boundaries. Remote/cloud tasks are outside local coverage unless their artifacts are present locally and their source is identified.

- Background coverage selects the internal/system disk and one development disk (auto-resolved from `~/develop`, or explicitly pinned); other external storage is excluded. Show each selected disk with separate metrics and capacity history.
- Observe machine/volume capacity as context and development storage as the primary subject. Overall disk growth can include unrelated applications and must retain an unattributed category.
- Discover relevant locations globally: Codex state, worktrees and task artifacts; project/build outputs; dependency/build caches; and tools invoked by Codex, including Xcode, simulators and Docker-backed storage. Recognize shared tool stores without claiming that their entire contents belong to Codex.
- Use lightweight lifecycle events, background bounded directory discovery, periodic/event-driven refresh and retained baselines. Do not synchronously traverse the whole disk before and after every tool call.
- Collect metadata and evidence across concurrent sessions, long tool invocations and bounded follow-up observation for background descendants. Record gaps, unsupported environments, missed events and permission limits.
- Keep one stable machine configuration and history outside projects and versioned plugin caches. Hooks, MCP and a background worker must resolve the same location without per-chat setup. Root additions and exclusions belong to global settings; discovery must expose its actual coverage.
- Prioritize large occupancy, substantial/rapid growth, many files, sustained accumulation and relevant disk-pressure changes. Low-impact changes should remain quiet.

### Alerts are required behavior

An effective monitor must reach the user when a new finding merits attention. A query-only report or a log entry is not delivery of an alert. A dedicated dashboard remains optional; a working supported local notification/conversation-delivery adapter is a core requirement. The exact supported delivery surface must be verified before promising it.

Each alert includes the path/category, bytes or file-count change, time window, associated sessions/tools where evidence exists, confidence/coverage, and a non-executing next step. Deduplicate shared/overlapping findings; provide cooldown, acknowledgement and re-alert only for materially changed conditions. Incomplete coverage must not become a zero-growth success or an exact-growth alert. A pre-existing large artifact must not be announced as newly created growth merely because it was first discovered.

Detailed reconstruction of old sessions is not an automatic side effect of enabling the monitor. Existing occupancy may seed a baseline, but the historical-analysis workflow below requires the user's explicit request.

## 2. Historical occupancy analysis on explicit request

An instruction such as “分析已有 Codex 会话占用了多少空间” starts an on-demand local investigation. It must work even if no plugin snapshots exist. The analysis measures surviving artifacts now and looks for relationships to older Codex sessions, including sessions before the plugin was installed or enabled.

The investigation should:

1. Discover available local Codex session/task/worktree/artifact records, including archived sessions when accessible. Declare source locations, format/version support and coverage. An absent or unsupported historical record is an evidence gap.
2. Read the minimum necessary structured metadata and, when needed for this explicit investigation, relevant saved tool/artifact records. Extract references to workspaces, worktrees, outputs, build results and external-tool locations. Do not retain or export raw prompts, transcripts, command text, credentials or environment values.
3. Verify referenced paths against the current filesystem. A mentioned path, planned command or successful command status alone does not establish that a file was created, survives today, or is exclusively owned by the session. Missing artifacts contribute no present occupancy.
4. Measure current allocated/logical bytes and file counts with bounded traversal. Rank heavy hitters and explain shared dependencies, caches, runtimes and worktrees separately from task-specific outputs.
5. Preserve evidence references and uncertainty for each session/path association. Deduplicate paths, parent/child buckets and hardlinked files. Shared occupancy may be associated with several sessions but appears once in global totals; session totals are not additive when ownership overlaps.
6. Return a report with the measured current occupancy, related sessions/projects/tool families, evidence category, uncovered areas and optional review recommendations. No automatic deletion or cleanup command execution follows.

### Evidence and time are separate dimensions

| Evidence category | Meaning | Permitted conclusion |
| --- | --- | --- |
| Recorded association | An available historical record explicitly links a surviving artifact/path to a session or task; the link and present path have been checked | Current occupancy associated with that record. Creation or exclusive ownership needs separate evidence. |
| Candidate association | Workspace, tool layout, timestamps or other indirect clues suggest a relationship | A candidate requiring review; excluded from a confirmed Codex-associated subtotal. |
| Unattributed | No sufficient session/task evidence, including general machine growth or a shared store without usable links | Present occupancy or volume change with unknown origin. |

A separate time-evidence field distinguishes **measured interval growth** from **current occupancy with no historical baseline**. A plugin baseline is not required to analyze pre-enable occupancy. Conversely, a first scan, file modification time or old session reference cannot invent pre-enable growth, peak usage, creation time or inactivity. When historical sources have no usable before/after measurements, historical growth remains unknown even if the current surviving bytes are measurable.

## Shared architecture and user experience

Both functions use the same storage inventory, heavy-hitter ranking, evidence model and local history. Global monitoring writes new observations; historical analysis enriches evidence on explicit request. Either feature can explain results without pretending that temporal correlation proves process ownership.

Machine-wide capacity is context for Codex storage management, not a claim that every byte on the machine was produced by Codex. “All sessions” means all supported local sessions within declared host coverage; it is not an exclusive-ownership or full-filesystem-readability promise.

Normal use should require one global enablement and no per-chat root configuration. Advanced settings allow scope/exclusions, budgets, retention and alert preferences. A status query should report monitor/worker health, shared configuration/state location, discovery progress, covered hosts/volumes/roots, recent gaps, alert-delivery health and available historical evidence sources. Version 0.4.3 returns worker/root/volume status, daily summaries, a read-only panel and coverage; installed real-host acceptance remains separate.

Historical analysis has its own explicit MCP operation with a clear indication that it can read local historical evidence, perform bounded measurement and persist a derived index. Do not silently change the existing read-only `footprint_report` operation into an expensive historical investigation. Version 0.2.0 adds a write-annotated `footprint_analyze_history` operation and version-2 configuration while preserving version-1 history.

## Delivery and acceptance stages

Write black-box E2E scenarios before the corresponding runtime changes. Each run retains a report with exact commands, environment/prerequisites, input recipes and actual results; process files and full logs are removed. Source tests and simulated hook inputs do not replace a real Desktop session or a real user-visible alert.

| Stage | Required acceptance |
| --- | --- |
| A. Shared global foundation | One enablement/state location across Hooks, MCP and worker; two concurrent sessions in different projects; multiple plugin instances coalesce to one worker; restart/upgrade preserve history; disabled state stays quiet; missing roots/permissions and worker failures are visible; bounded/fair scanning avoids hook stalls; volume samples and artifact bytes remain distinct. |
| B. Monitoring and alerts | A real external writer creates substantial storage during/between tools; concurrent/long-running/background work has declared coverage; meaningful growth reaches the user; repeated unchanged findings remain quiet; new material growth can re-alert; incomplete scans do not create exact-growth alerts; existing occupancy is not labeled new growth. |
| C. Historical analysis | A fixture creates artifacts and successful historical references before any plugin database exists; explicit analysis finds surviving occupancy and evidence links; no user request means no deep history reconstruction; moved/deleted paths, ambiguous timestamps, planned commands, unknown record formats, inaccessible/archived records, shared caches, hardlinks, nesting and concurrent path changes yield honest coverage and no duplicate totals; pre-enable growth stays unknown without usable measurements. |
| D. Integrated personal acceptance | Install from WXY Codex Plugins, use actual trusted Desktop hooks across different chats, receive a visible actionable alert, then explicitly investigate a pre-enable artifact and verify the measured current bytes and evidence. Keep replayable reports only and record unresolved coverage. |

The current 0.4.3 runtime implements these flows within the limits documented in [implementation scope](v1-scope.md); automated tests do not replace integrated real-host acceptance. The panel and daily summaries read retained metadata; meaningful alert delivery and pre-enable historical analysis cannot be deferred out of the core product definition.

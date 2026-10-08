# V1 scope and acceptance boundary

The [product scope](product-scope.md) is the target definition. It requires both global monitoring/meaningful alerts after enablement and explicitly requested historical occupancy analysis, including pre-enable artifacts. Version 0.1.0 implements the foundation below; it does not complete either function.

## Implemented foundation

- Codex compatibility manifest and a WXY Codex Plugins marketplace entry, with the original independent repository preserved as initial provenance.
- Seven lifecycle adapters, fail-open hook handling, opt-in explicit roots and bounded metadata observation.
- SQLite history, same-scope session/turn baselines and tool-call windows.
- Large occupancy/growth, average growth rate, many files and sustained growth signals over plugin snapshots.
- Existing occupancy from a first scan and bounded top-file records. This does not associate pre-enable artifacts with old sessions.
- Five local MCP tools, CLI, non-executing cleanup review plans and reproducible local ZIP packaging.
- Black-box E2E fixtures using real files, an external writer process, packaged hook commands and MCP messages; isolated WXY installation and installed-copy verification with replayable reports.

## Remaining core work

- **Global monitoring:** one shared machine config/history, global discovery, volume-capacity history, fair background refresh, worker coordination/recovery and coverage across concurrent supported local Codex sessions and long-running tools.
- **Meaningful alerts:** user-visible delivery, deduplication, cooldown, acknowledgement and repeat behavior for materially changed findings. Alerts are required; a dedicated dashboard can remain later work.
- **Historical analysis:** explicit request-driven local historical sources, path verification, current occupancy measurement, recorded/candidate/unattributed association and shared-artifact deduplication. It must operate without pre-existing plugin snapshots. Historical growth remains unknown when no usable before/after evidence exists.
- **Installed host acceptance:** real Desktop lifecycle delivery, common Hooks/MCP/worker state resolution, actual observation overhead and a real visible alert. Installation, MCP connectivity and the user's hook trust alone do not prove these behaviors.

Verified external-process write ownership, transient peak tracking, daily rollups, reliable inactive-artifact inference, Docker guest internals and Windows support also remain unimplemented. Unsupported sources or environments must be explicit coverage gaps. The current runtime is not a continuously running system-wide profiler.

Personal local use remains the scope. No public-directory submission, reduced skills-only substitute, remote service, telemetry, cloud sync or deletion/execution tool is planned. WXY repository distribution and personal installation are separate from official-marketplace publication.

## Next bounded stages

1. **Shared global foundation:** unify global state, discovery/capacity inventory and bounded worker coordination. Preserve 0.1.0 data/compatibility and test across different projects/chats before claiming all-session coverage.
2. **Monitor and alerts:** exercise substantial real external-process growth, concurrency and long-running work, then deliver a meaningful user-visible alert and verify unchanged-state silence.
3. **Pre-enable historical investigation:** create old-session/artifact fixtures before initializing plugin history; explicitly analyze surviving occupancy and evidence, with missing/shared/ambiguous cases.
4. **Integrated personal acceptance:** run both functions from the installed WXY plugin in actual Desktop chats and retain replayable evidence. A panel can follow after the core functions work.

Write each stage's E2E scenarios before runtime implementation. The complete criteria are in [product scope](product-scope.md); no new runtime capability is activated by this documentation update.

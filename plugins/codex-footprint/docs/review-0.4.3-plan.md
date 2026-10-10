# Review regression plan — 2026-10-10

Five findings on PR #2 are reproducible code risks. Before implementation, exercise them through CLI/MCP/dashboard responses with temporary metadata fixtures; no unit tests, personal scans, model calls or real notifications.

- Missing external paths on Linux must not inherit `/` as ownership. Cover stale capacity/alerts/inventory, an offline explicitly selected development mount, selected internal fixtures and platform-independent missing `/Volumes` paths. Linux branch execution on macOS is a CLI bootstrap simulation and must not be called native Linux acceptance.
- `report`, `explain`, `cleanup-plan` and MCP equivalents must project background inventory/volumes before sorting, session/path filtering and limits. Keep explicit historical-analysis scope separate; do not erase retained metadata.
- Scoped daily coverage must use displayed roots, remaining pending endpoints and the closed daily window. Cover a removed incomplete outside root, incomplete selected root, selected pending root, unfinished day, empty scope and missing window metadata. Projection must not rewrite saved report evidence.
- Hook scan progress must be separate from actual emission IDs. Cover mixed and outside-only batches, changing selected volume, more than 100 excluded records before an eligible record, legacy empty-ID watermark, actual recorded IDs, acknowledgement, opt-out and concurrent clients. Limit each hook to a bounded batch and reset its scan cursor when volume scope/availability changes.
- Each disk's pending count must include all retained unacknowledged selected findings, independently of the recent 100-item detail list. Cover 130 internal findings, acknowledgement and excluded external findings.

Retain replay commands, environment, input recipes and results only; delete temporary databases, bootstrap scripts, profiles and subprocess artifacts after each run. After targeted regressions pass, run the installed-copy acceptance once, upload the scoped fix to the existing PR and preserve personal config/history during upgrade. Do not merge without the user's merge request.

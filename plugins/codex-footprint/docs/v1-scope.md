# Implementation and acceptance boundary — 0.4.0

[Product scope](product-scope.md) remains the target contract. [Implementation plan](implementation-plan.md) orders A → B → C → D. The two functions now have a working local implementation; automated results and real host acceptance must be reported separately.

## Implemented

- Full WXY plugin manifest, seven guarded lifecycle definitions, nine local MCP tools and reproducible ZIP.
- One stable global config/history, lightweight spool, elected detached worker, fair resumable metadata walks and separate capacity samples.
- Global known-development-root/workspace discovery; complete comparable baselines, worker health and next-hook recovery; disable retains history.
- Growth/rate/file-count/large-threshold/sustained/capacity signals, durable inbox, acknowledgement, cooldown and material re-alert.
- Public macOS FSEvents dirty-root scheduling, periodic reconciliation and polling fallback; no per-file delta cache or persistent replay.
- Top-navigation read-only panel with 1h/24h/7d capacity chart, numeric GB axis and interval delta.
- Nonblocking active-chat hook notices with global concurrent deduplication; idle chats are not woken.
- macOS native notification adapter with honest accepted/failed/unverified-visibility delivery state.
- Explicit current/archived JSONL historical analysis without old snapshots; surviving occupancy, source/line evidence, recorded/candidate association, missing paths and shared/hardlink deduplication.
- Version-1 configuration backup and untouched legacy database compatibility.

## Automated evidence

The test-first black-box suites cover the legacy transport/accounting flow, new global operation and failure/compatibility boundaries. They create real files through external processes, concurrent hook clients, an elected background worker, a crash/recovery, long-running writes without PostToolUse, explicit pre-enable history, and actual MCP exchanges. Installed-copy E2E verifies marketplace packaging and source hashes. Reports retain commands, prerequisites, input recipes and actual results only; see [verification](verification.md).

No automated fixture proves that a real Desktop chat delivered its hooks or that a native banner was visible. Native notification acceptance must remain separate from command success. Personal run receipts belong in the delivery artifacts rather than an unconditional all-host claim.

## Remaining limits

- Local supported hooks/roots only, not remote/cloud sessions or whole-disk readability. Discovery may miss custom external tool stores; configure them globally if needed.
- Temporal/path correlation, not verified process ownership, exclusive session totals or global per-turn byte accounting.
- Live metadata walks; restart loses unfinished in-memory cursors. Short-lived peaks can be missed. An optional macOS user service restores failures/login; public file-event hints trigger bounded root remeasurement. Native event-loss flags are handled conservatively but not yet induced in E2E.
- Monitor root totals are not additive across shared hardlinks/time windows. Explicit history deduplicates globally.
- Bounded historical analysis may return partial lower bounds; no durable resume job, unsupported formats/paths remain gaps. No raw transcript retention, age-based inactivity claim or invented historical growth.
- Docker guest internals, APFS exact reclaim and Windows observation remain future work. The read-only panel and metadata daily rollups are implemented; daily Codex reminders require a separately configured scheduled chat; anomaly hook notices require an active chat operation.
- Large-machine baseline completion/overhead, across-chat host coverage and OS-visible delivery require ongoing personal acceptance.

No official-marketplace submission, reduced skills-only substitute, remote service, telemetry/cloud sync or deletion/execution tool is included.

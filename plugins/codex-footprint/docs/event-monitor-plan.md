# Event monitoring and portrait dashboard — 2026-10-08

Implement in order: black-box acceptance → native event adapter/monitor integration → chart retention and responsive panel → nonblocking Codex hook notices → real host installation and acceptance. No subagents, cloud transport or routine whole-disk/history scan. Preserve unrelated marketplace work, existing history and running chats.

## Failure and acceptance map, before implementation

- Native loading/stream creation/start/thread failure: expose a polling fallback and its reason, retry with backoff; never report native coverage when unavailable. Explicit polling and unsupported platforms remain usable.
- Events coalesce, arrive in bursts, or carry dropped/wrapped/root-change flags: bounded dirty-root state, conservative rescan of monitored roots after loss; no raw filesystem event history. Events are hints, not byte measurements or process ownership.
- Changes during a resumable scan: retain a follow-up dirty root; do not discard events on scan completion. Start listening before baseline work. A restart rebuilds baselines; no claim of persistent event replay.
- Root addition/removal, root rename/delete/recreation, exclusions and observer-state writes: reconcile watcher scope, ignore excluded/state paths, mark missing/inaccessible roots incomplete, periodically reconcile even when no event arrives. Changed roots refresh under the existing fair entry/time budget; no per-file delta cache in this release.
- Quiet trees: completed baselines remain idle between events/low-frequency reconciliation. Lifecycle events keep correlation metadata without forcing unchanged trees to rescan.
- Volume samples: retain minute buckets for seven days separately from short snapshot retention. Preserve existing samples during migration; bound database and chart response, preserve extrema while downsampling, keep device identities separate. Missing older history remains missing.
- Chart: 1-hour/24-hour/7-day selection, actual observed timestamps, numeric GB vertical axis and interval change; flat/single/missing samples remain honest. Top navigation must fit portrait windows without consuming a permanent left column. Test real browser behavior at narrow and wide sizes.
- Codex notices: supported SessionStart/UserPromptSubmit/PreToolUse/PostToolUse output only; no stop/block/permission/input rewrite. Global dedup across concurrent chats, at most three concise findings, disabled/acknowledged/unavailable/locked state stays quiet. Emitted hook output is not proof of a visible warning; idle chats cannot be awakened through hooks. Paths are untrusted data, never instructions or deletion authorization.

## Verification

Use real workers, actual FSEvents and external writers in temporary local directories. Exercise native idle/change/exclusion/burst/root-change, dynamic scope, explicit polling, long chart retention and concurrent hook output. Report exact recipes, commands, environment and observed results; remove generated files/processes. Native event-loss flags cannot reliably be generated end to end; the adapter must conservatively invalidate coverage on those flags and disclose this remaining fault-injection gap. Do not add isolated tests unless that gap requires them, and enumerate the full isolated failure contract first.

Real host acceptance: safe upgrade, runtime/source fingerprints, healthy native stream, low-overhead sample, real Codex hook warning and model-context receipt when obtainable, responsive panel navigation/range controls. Actual visible delivery and first scheduled 21:00 summary are separate from JSON protocol success.

Real-host discovery (2026-10-08): launchd can start a worker with a 256 soft file-descriptor limit. WatchRoot requires multiple descriptors per root/ancestor; 60 actual roots fail stream creation at 256 but succeed with a larger per-process allowance. Cover this with a real worker launched at 256 and 60 temporary roots before changing resource handling. Raise only the worker process soft limit within the inherited hard ceiling, bounded to 8,192; never change system settings or hard limits. A hard ceiling/refused raise must still use polling honestly. Existing traversal cursor budgets remain conservative.

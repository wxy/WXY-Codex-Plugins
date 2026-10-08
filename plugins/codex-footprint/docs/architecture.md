# Architecture — V1

Codex Footprint is a Codex-specific development storage growth monitor. The first implementation is local, metadata-only and non-destructive. The [product contract](product-scope.md) defines two required functions: global monitoring with actionable alerts, and explicit historical analysis including pre-enable artifacts. The first sections below describe the shipped 0.1.0 foundation; the target architecture at the end is not implemented. Personal local use takes priority over public distribution.

```mermaid
flowchart LR
  C[Codex lifecycle events] --> H[Fail-open hook adapter]
  H --> S[Observation service]
  M[Local MCP tools] --> S
  CLI[Local CLI] --> S
  S --> O[Bounded storage observer]
  O --> DB[(Local SQLite history)]
  DB --> E[Heavy Hitter Engine]
  E --> R[Versioned reports and explanations]
  R --> P[Review plans]
  R -. future .-> UI[Panel / notifications]
  PE[Future process evidence adapter] -.-> S
```

## Source boundaries

- `config.py`: opt-in roots, strict schema, scan budgets, root-overlap rejection, scope identity and retention validation.
- `observer.py`: local directory metadata traversal. Tracks allocated and logical bytes, entry/unique file counts, non-overlapping directory buckets, hardlink duplicates, top files and incomplete coverage. No regular file content is opened.
- `store.py`: schema-versioned SQLite events and snapshots, a serialized capture transaction, rollback journaling and bounded retention.
- `engine.py`: first/retained/task baselines, heavy hitters, tool windows, explanations and non-executing review plans. Snapshot maps are prepared once per report; analysis scales with retained bucket observations rather than repeatedly scanning the filesystem.
- `service.py`: shared transport-independent operations and hook metadata normalization. The root set comes only from explicit configuration. Read queries use a read-only database connection; they never initialize an empty history.
- `mcp.py`: local stdio MCP adapter with five tools, JSON-RPC initialization, strict tool arguments and bounded input messages. No network listener, filesystem mutation tool or UI capability.
- `cli.py`: local entrypoint and fail-open hook boundary. Packaged scripts resolve source paths from their own location.
- `packaging.py`: allowlisted reproducible local package construction, including complete lifecycle hooks, MCP wiring and documentation.

## Event contract and ordering

SessionStart establishes a session observation. UserPromptSubmit establishes a turn observation. PreToolUse/PostToolUse bracket tools using session ID + turn ID + tool-call ID. Stop captures the last turn observation. SessionEnd and Interrupt record metadata only, avoiding a traversal under the short interrupt budget.

Hooks remain synchronous so a pre-snapshot finishes before the tool begins. Each observation has a shared time/entry budget across all roots; SQLite `BEGIN IMMEDIATE` serializes captures so competing hook processes cannot commit stale scans out of order. Rollback journaling allows system-Python read-only SQLite connections to reopen a closed history without initializing WAL sidecars. Readers see committed history; captures serialize, and a busy/locked database is a visible fail-open observation gap. Other processes may write during traversal; this is not an atomic filesystem snapshot. A busy database, invalid configuration, malformed input, permission denial or scan exception leaves a stderr diagnostic and exit 0, with no stdout or Codex decision fields. Timeout/kill safety relies on the host continuing after a failed observer hook; real-host validation is still required.

The adapter stores only allowlisted event fields. Executable-family hints are labels inferred from the first command token, not process evidence. No command arguments, prompt text, transcript, tool output, PID ownership or environment values are stored. Calls to the observer's own MCP tools are ignored by the hook adapter to avoid feedback loops.

## Measurement and attribution

Directory buckets form a partition: root-level files use the root bucket, deeper files use up to `bucket_depth` directory segments. Root totals and bucket totals must not be added together. Hardlink inode identities are deduplicated across roots in configured order; file-entry counts still include hardlink names. APFS clones/shared extents and filesystem metadata are outside this accounting model.

A scope hash includes canonical roots, observer settings, exclusions, data directory and accounting version. Configuration scope changes cannot silently subtract incomparable snapshots. Threshold and retention changes do not change measured scope. Default reports compare the first and latest retained observations in that scope. Task reports require their own SessionStart or UserPromptSubmit baseline; a retained PostToolUse cannot fabricate a missing pre-baseline.

A comparison requires complete endpoints. Partial snapshots display lower-bound observed occupancy and diagnostics; numeric growth and rates remain unknown. Sustained growth requires multiple positive complete intervals; unchanged observations neither add to nor reset the streak, shrinking or incomplete observations reset it. In the current snapshot engine, "historical" means retained baseline occupancy. This is narrower than the product's required pre-enable historical investigation, which needs a separate evidence adapter; neither a baseline nor a path reference proves pre-install growth or inactivity.

Tool windows are temporal correlations. Concurrent tasks, external writers, OS services, Docker daemons and background children prevent unique ownership. Windows may overlap and must not be summed. Large and numerous files can be useful artifacts. Every cleanup plan declares execution unsupported and reclaim unknown.

## Planned extensions

The observer's snapshot DTO and report `schema_version` are integration boundaries for alerts, a panel and process-evidence adapters; version changes must preserve old history and explicit coverage semantics. A user-visible alert adapter is required for the global monitor. The optional panel can follow later. Clients should display coverage/attribution beside metrics. Notifications must deduplicate new actionable signals and must not be triggered by an incomplete scan treated as zero usage.

Future process evidence should attach PID, parent identity, process start time, executable classification, evidence source and limitations. PID alone cannot establish causation. A companion/daemon may enable in-tool periodic observations and descendant tracking, but needs its own lifecycle, permissions, CPU/IO budgets and supported installation model. None is active in V1. Remote services and cloud sync are outside current personal-local scope.

## Operational limits

Default history is 500 snapshots and 5,000 events, with at most 100,000 scanned entries per snapshot. Per-scan data is bounded but aggregate metadata can still be substantial; SQLite freed pages are reused rather than automatically vacuumed. Historical daily rollups, database byte ceilings, fair scheduling among large roots, filesystem notifications, periodic in-tool observation, verified process attribution and daemon recovery are future work. A large first root can exhaust the shared budget before later roots, which remain explicitly incomplete.

## Target architecture — both core functions (not implemented)

```mermaid
flowchart LR
  C[All supported local Codex sessions] --> H[Lightweight lifecycle evidence]
  H --> W[One global bounded observer worker]
  V[System volume capacity] --> W
  D[Global path discovery and refresh] --> W
  W --> DB[(Shared inventory, evidence and history)]
  U[Explicit historical-analysis request] --> A[Read-only local history adapter]
  A --> X[Verify surviving paths and measure occupancy]
  X --> DB
  DB --> E[Heavy hitters and evidence-aware analysis]
  E --> N[Deduplicated meaningful alerts]
  E --> M[MCP explanations and review plans]
  E -. optional .-> P[Panel]
```

- **Global coordination:** one machine config/state location is resolved consistently by Hooks, MCP and worker, independently of project, current chat and plugin cache version. Coalesce multiple clients; serialize/cancel bounded work, recover from crashes and retain discovery progress/coverage. Avoid full directory traversals on every synchronous hook. Disabling observation stops new background work without erasing history.
- **Capacity and inventory:** sample system-reported volume capacity separately from allocated file-block inventory. Discover Codex/project/external-tool locations across sessions, refresh fairly under IO/CPU budgets and record inaccessible/unclassified areas. Shared stores and unrelated volume changes remain explicit; global disk growth is not automatically Codex growth.
- **Post-enable evidence:** associate volume/inventory observations with lifecycle windows and any available process/artifact evidence. Concurrent sessions and background descendants require overlap-aware accounting and coverage. Temporal correlation and exclusive process ownership remain separate claims.
- **On-demand history adapter:** only an explicit historical-analysis request starts old-session reconstruction. Discover versioned local session/task/worktree/artifact records read-only, extract minimal needed links, verify current paths and produce a derived evidence index. Reading relevant saved tool records for this request does not authorize raw transcript/prompt/command retention. Missing, moved, planned-only, ambiguous or unsupported evidence stays visible.
- **Evidence model:** keep association class (`recorded`, `candidate`, `unattributed`), evidence references and limitations independently from time evidence (`observed_interval`, `no_baseline`). Store current occupancy and measured growth as distinct values. Deduplicate shared/parent-child/hardlinked storage globally; sessions may reference the same artifact without owning additive byte totals. Exact schemas are pending implementation.
- **Alerts and queries:** persist finding identity/acknowledgement/cooldown and route meaningful new conditions through a supported, tested user-visible adapter. Read-only queries stay read-only. A separately named explicit historical-analysis operation may trigger bounded work and write a derived index; the existing `footprint_report` must not silently acquire those side effects. A first discovery of an old large directory is not new growth.

See the staged E2E and real-host acceptance criteria in [product scope](product-scope.md). This diagram is a development target, not evidence that a worker, historical adapter or alert delivery is currently active.

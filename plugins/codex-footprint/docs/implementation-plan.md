# Implementation plan — 2026-10-08

This plan implements the two functions in [product scope](product-scope.md). Work proceeds A → B → C → D. Each stage starts with black-box failing E2E scenarios; reports retain commands, environment, inputs and outputs. Existing 0.1.0 history is preserved. No deletion, remote service or public-directory work is included.

| Stage | Change | Acceptance and stop condition |
| --- | --- | --- |
| A: global foundation | Stable machine state; explicit global enable/disable; lightweight event spool; one detached observer; automatic Codex/development/tool discovery; fair resumable metadata traversal; volume samples; worker health/recovery | Different project/session events share one inventory. Concurrent starts elect one worker. Incomplete scans are visible, bounded and resumed; no invented growth. Disable stops work. Legacy snapshot history remains readable. Stop on corruption, hook stalls or scope/permission ambiguity. |
| B: meaningful alerts | Persisted findings, acknowledgements/cooldown; substantial/rapid/sustained growth and file-count signals; macOS desktop adapter; queryable alert inbox | External writer produces one actionable finding; unchanged conditions stay quiet; materially greater growth can re-alert. No baseline/incomplete endpoints produce no exact-growth alert. Native command success is separate from observed user-visible delivery. |
| C: historical analysis | Explicit analysis operation independent of monitor enablement; read-only current/archived local session adapters; surviving path measurement; recorded/candidate/unattributed evidence; shared/hardlink/nesting deduplication | Artifacts and session records predate the plugin DB; explicit operation finds surviving occupancy with unknown pre-enable growth. Planned commands do not establish creation. Missing/unknown/oversized/inaccessible evidence stays explicit. Raw prompts/commands are not retained. |
| D: personal delivery | Versioned WXY package; installed-copy E2E; migrate/retain old caches and state; enable once; actual host event and notification verification | Source and installed runtime match. Real host lifecycle evidence is distinguished from synthetic inputs. Desktop alert needs visible evidence or explicit user confirmation. Publish scoped review branch/PR updates without merging. |

## Runtime choices

macOS first, Python >=3.9 and stdlib. A single-worker filesystem lock coalesces plugin clients. Hooks append small allowlisted events and ensure the worker is running; metadata traversal happens in worker slices, not synchronously in every hook. New monitor storage uses a separate versioned SQLite schema, leaving the original snapshot database intact. Readers do not initialize absent state.

Global defaults use a stable XDG state location rather than host-provided per-plugin `PLUGIN_DATA`. Explicit `CODEX_FOOTPRINT_DATA`/`CODEX_FOOTPRINT_CONFIG` remain available. Existing version-1 explicit-root operation remains supported. Discovery includes existing Codex/development/tool paths and workspaces observed through trusted lifecycle events; status exposes exclusions, missing permissions and supported local coverage.

Historical reconstruction is only user-requested and gets a distinct write-annotated MCP operation. Supported evidence adapters are explicitly versioned; workspace context is a candidate association, while checked structured artifact references are recorded associations. Neither proves exclusive ownership. Measured present occupancy and temporal growth are distinct fields.

Notification delivery uses the documented macOS native notification command. System settings may suppress it, so delivery status must say command accepted/unverified rather than silently claim a visible banner. Alert inbox/acknowledgement remains available. Official sources: [Codex hooks](https://learn.chatgpt.com/docs/hooks), [Apple notifications](https://developer.apple.com/library/archive/documentation/LanguagesUtilities/Conceptual/MacAutomationScriptingGuide/DisplayNotifications.html).

## Evidence

Each E2E runner writes `report.json`, `report.md`, and a bounded transport/process transcript. Real-host acceptance records host version, source/installed hashes, event IDs, baseline/latest IDs, measured growth, native-delivery outcome and any remaining gaps. Fixture notifications are separate from production findings and do not fabricate real session evidence.

## Delivery status — 2026-10-08

A/B/C runtime and automated scenarios are implemented in 0.2.0. Three installed-copy suites passed: 19 legacy + 15 global + 14 edge cases (48 total). Existing 54 WXY regressions also passed. Personal installation matches 41 tracked plugin files, keeps the seven trusted hook definitions unchanged, preserves old hook paths/other plugins and enables the shared observer. Real events from two local Codex chats have reached the same worker/database. A labeled native notification probe was accepted by macOS and explicitly confirmed visible by the user.

D is partial real-host acceptance: first large-machine baselines are still building; actual production-growth notification visibility, complete cross-project baselines and sustained overhead remain open. No full investigation of private historical sessions was started implicitly. Source test fixture history does prove the pre-enable flow; the user's own history waits for an explicit analysis request. A fresh chat is needed to load the new MCP tool set after upgrade.

A real-machine follow-up found unused entry budget with many roots. A failing 70-root black-box case precedes the scheduler correction: allocate slices across active walks while enforcing the total tick entry/time caps, and expose discovered/completed/pending counts in worker health.

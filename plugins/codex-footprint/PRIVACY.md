# Local data and privacy — 0.2.0

Codex Footprint is an independent developer plugin for Codex. It has no network client, telemetry, account, cloud synchronization or deletion endpoint.

The global worker traverses discovered/configured development roots for metadata only. It retains absolute paths, file-block/logical bytes, counts, coverage/errors, timestamps and minimal allowlisted lifecycle IDs/tool-family labels. It does not open ordinary artifact contents. Hook prompts, command text/arguments, raw tool output and environments are not retained. Paths/IDs can still contain personal information; keep reports private.

Only an explicit historical investigation reads supported local current/archived session JSONL, including saved structured tool outputs, to extract minimal path associations. It retains derived source-file/line references, association classes and measured surviving occupancy, never raw transcripts, prompts, command text, credentials or environment values. Enabling the monitor or querying normal reports does not perform this reconstruction. Historical source/measurement budgets and unsupported formats appear as coverage gaps.

Shared state resolves from `CODEX_FOOTPRINT_DATA`, else `${XDG_STATE_HOME:-~/.local/state}/codex-footprint`; per-plugin `PLUGIN_DATA` is ignored. `CODEX_FOOTPRINT_CONFIG` overrides config location, and `CODEX_HOME` identifies local host history/settings. State/config remain outside projects and versioned caches. Generated state uses private file permissions. SQLite read-only queries do not create absent state.

Default retention is 500 observations/capacity samples/findings/analysis results each and 5,000 events. Latest inventory is retained separately. SQLite may reuse freed pages rather than shrink immediately; no automatic vacuum or user-artifact deletion runs. Legacy configuration is backed up and the original snapshot database is preserved during global enablement.

A detached local worker runs after enablement/trusted hooks. Global disable or the WXY host plugin global toggle stops it on its next tick. History remains local. No login service is installed; a stopped worker restarts on a later trusted hook or explicit enable/scan.

Meaningful findings may send a macOS desktop notification with signal/bytes and a query prompt; paths are kept in the inbox rather than notification text. OS settings can suppress display. An optional inbox backend avoids native notification commands. MCP returns selected metadata into Codex when called; the conversation may therefore contain paths/IDs. The plugin itself does not upload them. Review any report before sharing it.

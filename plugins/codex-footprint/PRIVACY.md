# Local data and privacy

Codex Footprint 0.1.0 is an independent developer plugin for Codex. It has no network client, telemetry, account, cloud synchronization, filesystem content reader or deletion endpoint.

Configured roots are traversed for metadata only. Retained SQLite records include absolute directory/file paths, allocated/logical byte counts, file counts, coverage/errors, observation timestamps, and minimal Codex event metadata (session, turn, tool-call identifiers, tool name and an allowlisted executable-family hint). Prompts, transcripts, command text, arguments, process environments and file contents are not retained. Filesystem paths can still contain personal information; treat reports as private.

The state directory uses `CODEX_FOOTPRINT_DATA`, then `PLUGIN_DATA`, then `${XDG_STATE_HOME:-~/.local/state}/codex-footprint`. Prefer a stable `CODEX_FOOTPRINT_DATA` shared by hooks and MCP. Configuration comes from `CODEX_FOOTPRINT_CONFIG` or `config.json` in that state directory. Configuration is opt-in and never written into a project automatically.

Retention defaults to 500 snapshots and 5,000 events. Metadata is bounded by the scan entry/time budget and top-file limit, but SQLite may retain freed pages for reuse; logical retention is not an immediate reduction in the database file's high-water size. No vacuum or deletion of user artifacts is automatic. To stop monitoring, disable the plugin or set `enabled` to false. Historical state remains local; the user can remove that state directory after disabling the plugin.

MCP returns selected metadata to the Codex conversation when its tools are called. That can place paths and identifiers in the conversation. The plugin itself does not upload them. Do not publish a raw report without reviewing its paths.

## Planned historical analysis boundary

The [target product scope](docs/product-scope.md) adds an explicitly requested local investigation of pre-enable artifacts. This is not implemented by 0.1.0. It may read minimum necessary local historical session/task/worktree/artifact metadata and relevant saved tool records to establish path associations. It must retain derived evidence references and measurements without storing raw prompts, transcripts, command text, credentials or environment values. Enabling global monitoring alone does not start deep reconstruction of old sessions. Reports must distinguish recorded associations, candidates, unattributed occupancy and unavailable historical growth.

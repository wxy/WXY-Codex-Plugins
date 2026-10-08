# Migration provenance

On **2026-10-08**, the user requested that Codex Footprint join the existing **WXY Codex Plugins** repository and personal marketplace.

- Imported source: independent `codex-footprint` Git repository, commit `0e0f2c8e1d589c45ea022d2fc4b9f46c56e82780` (initial local V1).
- Canonical maintenance path: `plugins/codex-footprint/` in `wxy/WXY-Codex-Plugins`.
- Normal plugin identity: `codex-footprint@wxy-codex-plugins`, initial version `0.1.0`; global-monitor update `0.2.0`.
- Original independent checkout and its signed commit remain preserved as the initial snapshot. This import copies tracked project files only; it does not embed a nested `.git`, observation database, artifacts, caches or temporary test profiles.
- The shared catalog appends one entry. Existing Daydream and PR Title Hook entries retain their policies and paths.
- Runtime observation/analysis behavior is unchanged by this integration; primary installation docs now point at WXY. The standalone convenience catalog remains solely for self-contained archive tests.

Continue development here to avoid divergent source copies. Personal marketplace availability, personal installation/enabled state, configured observation scope and trusted/working host hooks are distinct states; a catalog entry alone does not establish live monitoring.

# Codex Footprint development

- Read `docs/product-scope.md`, `docs/v1-scope.md` and `docs/distribution.md` before changing product behavior. Two core goals: global post-enable monitoring with meaningful alerts; explicit historical occupancy analysis including pre-enable artifacts. Personal local use, honest coverage and low overhead take priority.
- Default to black-box end-to-end tests. Leave replayable reports, logs and exact commands/inputs/environment. If unit tests are truly needed, enumerate failure modes and write those tests before implementation.
- Never add automatic deletion, cleanup execution, prompt/command/transcript retention, cloud uploads or whole-home/disk scanning as a routine implementation choice.
- Global discovery/background observation is an approved product target, not permission for repeated synchronous full-disk walks in hooks. Use shared machine state, bounded fair work and explicit coverage. Detailed historical reconstruction requires the user's explicit analysis request; reading relevant historical records does not authorize raw content retention.
- Preserve coverage and attribution distinctions: partial scans give unknown growth; hook correlation is not process ownership; first observations are not retroactive growth evidence.
- Pre-enable current occupancy analysis does not require old plugin snapshots. Separate recorded/candidate/unattributed associations from measured interval growth, and count shared artifacts once globally. Meaningful alert delivery is core; the dedicated panel is optional.
- Official marketplace work is outside current scope. Do not build a reduced skills-only substitute, remote service or cloud sync unless the user explicitly reopens that direction. Historical platform research is archived under `docs/history/`.
- Keep temporary external reference material under a task-specific system temporary directory. Runtime state and fixtures must not enter Git. See README for the acceptance command.

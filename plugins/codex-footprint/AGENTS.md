# Codex Footprint development

- Read `docs/v1-scope.md` and `docs/distribution.md` before changing product behavior. Current goal: a complete personal local Codex plugin. Prioritize actual task observation and low overhead.
- Default to black-box end-to-end tests. Leave replayable reports, logs and exact commands/inputs/environment. If unit tests are truly needed, enumerate failure modes and write those tests before implementation.
- Never add automatic deletion, cleanup execution, prompt/command/transcript retention, cloud uploads or whole-home/disk scanning as a routine implementation choice.
- Preserve coverage and attribution distinctions: partial scans give unknown growth; hook correlation is not process ownership; first observations are not retroactive growth evidence.
- Official marketplace work is outside current scope. Do not build a reduced skills-only substitute, remote service or cloud sync unless the user explicitly reopens that direction. Historical platform research is archived under `docs/history/`.
- Keep temporary external reference material under a task-specific system temporary directory. Runtime state and fixtures must not enter Git. See README for the acceptance command.

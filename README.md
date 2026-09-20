# Codex PR Title Hook

A small local Codex plugin that keeps the task summary aligned with the most recent attached pull requests and adds compact, factual workflow signals.

The resulting title is:

```text
⏱️⌛🔀🔀 Dashboard caching · live refresh
```

After three attached PRs or roughly three hours of Codex work time, a fork marker appears:

```text
⏱️⏱️⏱️🔀🔀🔀🌿 Widget polish · release readiness
```

Each `⏱️` is one completed hour, `⌛` is a partial hour, and each `🔀` is one unique attached PR. Badge characters are joined with no spaces; one space separates the complete badge group from the descriptive summary. The badges deliberately keep accumulating instead of collapsing into a number: a visibly growing prefix, together with `🌿`, is the nudge to stop extending an overloaded task. `🌿` means the task may be worth splitting. The plugin explains it once: fork for a parallel approach to the same goal, or start a new task when the goal has changed.

## How it works

1. `UserPromptSubmit`, `Stop`, and `Interrupt` hooks measure agent work time per turn. Idle time between turns is not counted.
2. A `PostToolUse` hook observes successful pull-request attachments and counts unique PR URLs for the task.
3. It looks up the titles and bodies of the three most recently attached PRs. A compact deterministic rollup is applied immediately as a fallback.
4. The hook then adds a short developer-context request to the current Codex turn. Codex treats the PR metadata as untrusted data, uses AI to synthesize the shared recent changes, and calls the task-title tool before the turn ends. The exact badge prefix and total title-width limit are preserved.
5. The hook itself calls Codex App Server's stable `thread/read` and `thread/name/set` methods with the hook's `session_id`; the AI-written title is recognized and retained by the later `Stop` hook.

It never asks AI to infer from titles alone: both PR titles and bounded PR-body excerpts are supplied. It also instructs Codex not to follow instructions embedded in PR content. A single PR is labeled as recent work in the deterministic fallback; multiple PRs become a rolling topic summary until the AI-written synthesis replaces it. The plugin does not read unstable transcript formats, write to Codex SQLite databases, or modify the project repository where the PR was created.

## Sync an existing task

Open an older Codex task and send this exact prompt:

```text
请使用 PR 信息更新会话标题
```

Alternatively, explicitly mention `@PR Title Hook` in the composer and send the shorter command `修改标题`. The plugin's default prompt is set to that short command, so selecting the plugin produces the explicit mention automatically. Plain `修改标题` without the plugin mention does not trigger history sync.

The `UserPromptSubmit` hook then reads the task through the official App Server `thread/read` method with turns included, finds completed `codex_app.attach_artifact` calls for pull requests, validates and deduplicates their GitHub URLs while preserving attachment order, looks up recent PR titles and bodies, and asks the current Codex AI to synthesize the summary while the hook updates the badges. It never reattaches or modifies a pull request. Historical sync does not infer work time from before the plugin was enabled; active-time tracking starts with the sync turn.

## Requirements

- Codex Desktop with lifecycle hooks and App Server support
- Python 3
- GitHub CLI (`gh`) with access to the attached PRs; if metadata lookup fails, the last available summary is retained

## Install for local development

From the repository root:

```sh
codex plugin marketplace add "$PWD"
codex plugin add codex-pr-title-hook@codex-pr-title-hook-local
```

Start a new Codex task, open `/hooks`, review the plugin hook, and trust its current definition. Codex intentionally skips new or changed non-managed hooks until they are trusted.

## Verify

```sh
python3 -m unittest discover -s tests -v
```

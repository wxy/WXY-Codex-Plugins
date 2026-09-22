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

Each `⏱️` is one completed hour, `⌛` is a partial hour of at least ten minutes, and each `🔀` is one unique attached PR. Zero values produce no badge. Badge characters are joined with no spaces; one space separates the complete badge group from the descriptive summary. The badges deliberately keep accumulating instead of collapsing into a number: a visibly growing prefix, together with `🌿`, is the nudge to stop extending an overloaded task. `🌿` means the task may be worth splitting. The plugin explains it once: fork for a parallel approach to the same goal, or start a new task when the goal has changed.

## How it works

1. On task startup or resume, the plugin reconstructs approximate work time from completed-turn timestamps. Time inside a turn, including tool or approval waits, is counted; idle time between turns is not.
2. The same reconciliation scans completed pull-request attachments, so the persisted state is only a cache rather than the source of truth.
3. `UserPromptSubmit`, `Stop`, and `Interrupt` keep the current turn's elapsed time updated between reconciliations.
4. A `PostToolUse` hook observes successful pull-request attachments and immediately reconciles unique PR URLs for the task.
5. It looks up the titles and bodies of the three most recently attached PRs. A compact deterministic rollup is applied immediately as a fallback.
6. The hook then adds a short developer-context request to the current Codex turn. Codex treats the PR metadata as untrusted data, uses AI to synthesize the shared recent changes, and calls the task-title tool before the turn ends. The exact badge prefix and total title-width limit are preserved.
7. The hook itself calls Codex App Server's stable `thread/read` and `thread/name/set` methods with the hook's `session_id`; the AI-written title is recognized and retained by the later `Stop` hook.

The plugin is inactive for unrelated tasks. A task becomes managed only after a successful pull-request attachment or an explicit `@PR Title Hook`/fallback sync request. Lifecycle events for every other task return immediately without creating task state, reading the task, or changing its title. Hook commands are fail-open: a missing cached script or a handled runtime error cannot block the surrounding Codex task.

It never asks AI to infer from titles alone: both PR titles and bounded PR-body excerpts are supplied. It also instructs Codex not to follow instructions embedded in PR content. A single PR is labeled as recent work in the deterministic fallback; multiple PRs become a rolling topic summary until the AI-written synthesis replaces it. The plugin does not read unstable transcript formats, write to Codex SQLite databases, or modify the project repository where the PR was created.

## Sync an existing task

Open an older Codex task and explicitly mention `@PR Title Hook`. The mention itself is the command: no exact wording after it is required. For example, all of these trigger synchronization:

```text
@PR Title Hook
@PR Title Hook 修改标题
@PR Title Hook 请按最近的工作重新概括
```

The following exact text is also retained as a keyboard-friendly fallback when a plugin mention is inconvenient:

```text
请使用 PR 信息更新会话标题
```

The plugin's default prompt remains `修改标题`, so selecting the plugin produces a formal mention automatically. Plain `修改标题` without the plugin mention does not trigger history sync.

The `UserPromptSubmit` hook then reads the task through the official App Server `thread/read` method with turns included, finds completed `codex_app.attach_artifact` calls for pull requests, validates and deduplicates their GitHub URLs while preserving attachment order, reconstructs approximate completed-turn duration, looks up recent PR titles and bodies, and asks the current Codex AI to synthesize the summary while the hook updates the badges. It never reattaches or modifies a pull request.

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

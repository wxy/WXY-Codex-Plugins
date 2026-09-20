# Codex PR Title Hook

A small local Codex plugin that preserves the task's descriptive summary and adds compact, factual workflow signals.

The resulting title is:

```text
⏱️⌛ 🔀🔀 Fix dashboard refresh
```

After three attached PRs or roughly three hours of Codex work time, a fork marker appears:

```text
⏱️⏱️⏱️ 🔀🔀🔀 🌿 Fix dashboard refresh
```

Each `⏱️` is one completed hour, `⌛` is a partial hour, and each `🔀` is one unique attached PR. The badges deliberately keep accumulating instead of collapsing into a number: a visibly growing prefix, together with `🌿`, is the nudge to stop extending an overloaded task. `🌿` means the task may be worth splitting. The plugin explains it once: fork for a parallel approach to the same goal, or start a new task when the goal has changed.

## How it works

1. `UserPromptSubmit`, `Stop`, and `Interrupt` hooks measure agent work time per turn. Idle time between turns is not counted.
2. A `PostToolUse` hook observes successful pull-request attachments and counts unique PR URLs for the task.
3. The plugin preserves Codex's existing task title as the descriptive summary, then prepends the compact metrics.
4. It calls Codex App Server's stable `thread/read` and `thread/name/set` methods with the hook's `session_id`.

It does not use PR titles as task titles, read unstable transcript formats, write to Codex SQLite databases, or modify the project repository where the PR was created.

## Requirements

- Codex Desktop with lifecycle hooks and App Server support
- Python 3

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

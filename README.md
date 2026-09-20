# Codex PR Title Hook

A small local Codex plugin that renames the current Codex task after a GitHub pull request is successfully attached.

The resulting title is:

```text
PR #83 · Close out AI Pulse 2.0 release
```

## How it works

1. A `PostToolUse` hook observes a successful `mcp__codex_app__attach_artifact` call for a pull request.
2. The hook reads the PR number and title with the authenticated GitHub CLI.
3. It calls Codex App Server's stable `thread/name/set` method with the hook's `session_id`.

It does not write to Codex SQLite databases or modify the project repository where the PR was created.

## Requirements

- Codex Desktop with lifecycle hooks and App Server support
- GitHub CLI (`gh`) installed and authenticated
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
python3 /path/to/plugin/scripts/pr_title_after_pull_request.py --dry-run < hook-event.json
```

The dry run resolves the real PR metadata but does not rename a task.

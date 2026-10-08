# Background monitoring, daily summaries and read-only panel

Confirmed 2026-10-08: whole-disk/historical investigations remain explicitly requested operations. Project monitoring runs in the background. At 21:00 local time (Asia/Shanghai on the personal host), summarize retained monitoring evidence, update the panel, and report in Codex. Daily reporting must never invoke whole-disk traversal or historical reconstruction.

## Delivery

1. Make a complete, navigable read-only panel prototype with overview, projects, findings, daily summaries and explicit-analysis results. Show data age, incomplete coverage and unknown growth. No delete, cleanup, configuration or scan action in the panel.
2. Write black-box acceptance before runtime changes. Verify fair budget consumption, external growth during background work, no automatic history reads, retained daily endpoints despite observation pruning, idempotent daily publication, safe read-only HTTP, and supervisor recovery/disable behavior.
3. Improve fair metadata scheduling: use the available entry/time budget rather than only one small allocation per active root; prioritize recently active projects without starving other roots; expose duration and stale observations.
4. Provide an optional macOS LaunchAgent using a stable runtime entry and the existing elected worker lock. Unexpected worker exits restart; intentional disable remains quiet. Installation/removal are explicit operations. Preserve existing configuration and history.
5. Keep daily endpoints separately from the short rolling observation table. Summarize observed intervals only; a first sample, incomplete walk, scope change or missing endpoint must retain unknown growth. Never add overlapping directory/session totals. Daily reports are local derived metadata and contain no transcripts.
6. Serve a localhost-only, read-only panel. Only fixed GET routes are supported. Reject writes, invalid Host/Origin and unknown routes. The server opens no arbitrary files and the browser loads no external resources. Display recent findings and daily summaries from shared state.
7. Create one Codex chat scheduled task at 21:00, using the plugin's summary operation and panel link. Report the day and available coverage. Do not create worktrees or trigger scanning from the scheduled task.

## Notification boundary

Official desktop documentation describes chat completion, Activity and scheduled-task results. No documented arbitrary third-party background notification-center injection has been established. Use Codex scheduled results for the daily reminder. Supported trusted hooks can return a nonblocking warning and bounded additional context on the next active chat operation; this is not arbitrary notification-center injection and does not wake idle chats. Retain an inbox/panel and the system adapter for idle delivery. See [hook outputs](https://learn.chatgpt.com/docs/hooks). Do not label an accepted OS command as a visible Codex notification. Do not edit application internals or inject unattended model turns.

## Acceptance and retention

All generated test inputs, databases, full logs, browser profiles and service fixtures belong in a task-specific system temporary directory and are removed after the run. Keep only replayable test reports: commands, environment, input-generation method, pass/fail evidence and unresolved host acceptance. Tests cannot establish large-machine latency, OS-visible delivery, login restart or user approval of the panel by themselves.

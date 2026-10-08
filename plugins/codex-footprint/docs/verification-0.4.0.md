# Version 0.4.0 acceptance report — 2026-10-08

## Reproduction

On macOS with Python 3.14 and a compatible Codex CLI, from the WXY repository root:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/report-directory
```

The runner creates a disposable Codex profile, installs the actual local marketplace entry, compares source/runtime hashes and runs the packaged suites plus safe upgrade. It removes its profile, files, SQLite fixtures and subprocesses. It invokes no model, personal state or OS notification. Native cases require macOS public FSEvents; polling remains available on supported non-macOS hosts.

Test scenarios and known failure modes were recorded before implementation in [event monitor plan](event-monitor-plan.md). The first native/history/hook run failed all six new cases against the old runtime; both subsequent runs passed. Final installed-copy outcome: **66 passed, 0 failed** (19 legacy, 15 global, 14 edges, 9 dashboard/service, 6 event/history/hook, 3 safe-upgrade).

The six new cases use real external writes and workers: quiet-root scan suppression; excluded paths; substantial growth; burst coalescing; dynamic workspace scope; root move/recreation; explicit polling; seven-day minute retention with a two-snapshot cap; six concurrent hook clients with exactly one nonblocking output; opt-out/acknowledgement/disable silence. They verify no automatic historical investigation and no permission/input rewrites. Hook emission leaves user acknowledgement unchanged.

## Browser acceptance

Run the source CLI `panel --port 8767` using an isolated disabled configuration and a SQLite backup of existing personal metadata in a task temporary directory. No scanning or new historical analysis occurs. Inspect with Codex in-app browser controls:

- 390 × 844: document scroll width 390, chart width 270; numeric GB axis and interval change visible.
- 640 × 1000: document scroll width 640, chart width 520.
- 1280 × 900: document scroll width 1280, chart width approximately 650.
- Top navigation, project search and 1h/24h/7d selection work. Wide tables scroll internally; they do not expand the page or chart.
- Actual source coverage was 18:55–19:13; the chart states the recorded interval and does not invent older history.

A first narrow-screen run exposed grid minimum-content overflow; constraining grid children and table containers fixed it. Final screenshots were inspected, then discarded. The temporary server/state were removed and browser viewport restored. Only replayable reports remain.

## Explicit limits

Native dropped/wrapped-event flags cannot reliably be induced in this E2E setup. The adapter invalidates all watched roots conservatively, but that branch lacks injected-fault acceptance. Reconciliation and stream failures fall back to bounded measurement/polling; event hints do not provide byte deltas, writer ownership, persistent replay or an atomic snapshot.

Output JSON acceptance does not prove an actual Codex warning was visible. Official hooks support warning/context output, but this path requires a trusted active chat operation. It cannot wake idle chats; OS notifications, durable findings and the separately configured 21:00 summary supplement it. Login restart, first scheduled delivery and long-duration/native overhead remain personal-host acceptance gates; fixture timings are not machine-wide performance claims.

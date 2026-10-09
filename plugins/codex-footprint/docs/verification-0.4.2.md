# Version 0.4.2 dual-disk capacity acceptance — 2026-10-09

## Behavior and test-first evidence

The system/data disk and the selected development disk have independent observation/capacity series and four metrics each. Other external disks are excluded from background observation. Parent workspace aliases resolve to one canonical root. Existing retained metadata is preserved.

The old overview selected the first stored volume, which could be a stale external record with only two samples. Device IDs also change across reboot/remount. Capacity queries now match selected mount paths/retained aliases; the axes span the requested 1h/24h/7d interval, with numeric GB ticks and time/date labels. Unrecorded edges and gaps over five minutes stay blank. Old daily rows without stored volume attribution are not relabeled based on moved paths.

Before implementation, the new three CLI/API cases failed against the preceding runtime. After the user selected a dual-disk scope, the tests were revised and again failed before the corresponding implementation. A real headless Chrome run against the old UI also failed its range-axis acceptance. The earlier attempt without an installed Chromium executable was an environment failure and is not regression proof.

## Replay

From the WXY repository root, with Python 3.14.6, Codex CLI, macOS, writable system temporary storage and loopback:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/report-directory/installed
```

Installed-copy outcome: **72 passed, 0 failed**: 20 legacy, 15 global, 14 edges, 9 dashboard/service, 8 event/history/hook, 3 dual-disk capacity, 3 safe-upgrade. Installation uses a disposable profile; source/cache hashes match, unconfigured installation stays inactive, and the profile/fixtures are removed. The source HEAD in the initial report is the base commit because the tested changes were uncommitted; source/cache hashes identify the tested contents.

Optional browser replay (Node, Playwright and an existing Chrome executable):

```sh
PYTHONDONTWRITEBYTECODE=1 \
NODE_PATH=/Users/xingyuwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules \
CODEX_FOOTPRINT_TEST_NODE=/Users/xingyuwang/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node \
CODEX_FOOTPRINT_TEST_CHROME='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' \
python3 plugins/codex-footprint/tests/e2e_internal_chart.py --browser --output /absolute/report-directory/browser
```

All four cases passed, including browser checks at 400/1100 pixels for all three ranges: two disk columns, eight metric cards, labeled selected-window axes, no horizontal overflow and sparse records drawn at their actual times. Inputs are recreated under a system temporary directory: missing selected-disk fixture paths/aliases (no external artifact traversal), seeded multi-day minute metadata across changed device IDs, a stale unselected volume, and 30-second late-start records. Only reports persist; databases, browser profiles, scripts and processes are removed.

The browser check proves headless Chrome behavior. Actual Codex in-app rendering and user acceptance remain separate surfaces. This change does not test a new OS/Codex notification delivery mechanism.

## Personal installation and live panel

The safe updater installed 0.4.2, restored the 0.2.0–0.4.1 cached chat entrypoints, moved the stable runtime pointer and restarted the existing user service. Configuration SHA-256 remained `e00975caa238f2739fada2bb4fc0445f41987aa0d83f27392649a333193a16de`; both saved historical analyses remained, SQLite integrity was `ok`, and the healthy worker reported native FSEvents. Unrelated marketplace plugins/catalog were unchanged.

A read-only GET returned 200 and two capacity series. The internal disk retained 706 minute rows from the previous device ID plus the current-device history; 1h/24h/7d returned respectively 61/734/911 samples at the recorded checkpoint. MacSSD returned 61/207/207. These moving counts are checkpoint evidence, not future fixed assertions. No scan/history-analysis operation ran. The upgraded accounting scope requires new comparable project baselines.

Headless Chrome 154.0.8037.98 with Node 24.19.0 exercised the live URL at 400/1100 pixels and all three ranges. Both columns had four independent metrics, at least three labeled x ticks and three GB y ticks, correct selected duration, no horizontal overflow, stacked narrow placement and parallel wide placement, with no page errors. Temporary screenshots were visually inspected and removed after recording this report. Codex in-app browser control was unavailable due to the host sandbox's symlink-root initialization error; no actual in-app acceptance is claimed.

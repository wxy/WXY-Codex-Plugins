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

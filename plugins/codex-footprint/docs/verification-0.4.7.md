# Independent development-cache baselines — 0.4.7

## Problem and change

One unreadable child made the inclusive `~/Library/Caches` observation partial forever. Complete-only baseline rules correctly refused that parent, but also prevented readable development caches from obtaining comparable growth measurements.

The background worker now discovers named development-cache children independently. Shallow metadata discovery is bounded to 256 entries per 60 seconds; normal measurements keep the existing shared slice, file-event and reconciliation budgets. Protected/unreadable children, skipped development symlinks, missing anchors and discovery limits remain explicit unknown gaps. Other readable application caches are outside the named automatic scope. There is no permission request, permission modification or automatic deletion.

Explicit cache parents are partitioned too. Broader ancestors omit the cache subtree with absolute-path exclusions in the measurement fingerprint. Inclusive old parents remain historical, and cannot be mixed into split accounting. Read-only status/report/explain/panel operations consume retained discovery metadata. Daily snapshots and earlier partial evidence belong to their observation day.

## Environment and commands

macOS, ordinary user UID 501, native arm64 Python 3.12.14, installed Codex CLI and headless Google Chrome with a disposable profile. No personal plugin installation, login service, privacy settings or dashboard tab was changed. Test inputs are temporary HOME/cache/project trees, actual filesystem permission denials, lifecycle events and historical metadata fixtures. `Cellar` is excluded in the new fixture so automatic discovery does not walk the host's Homebrew installation. Unix permission denials do not prove macOS TCC behavior.

From the WXY repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 plugins/codex-footprint/tests/e2e_cache_coverage.py --output "$TMPDIR/cache-coverage-report.json"
PYTHONDONTWRITEBYTECODE=1 python3 tests/e2e_codex_footprint_marketplace.py --output "$TMPDIR/footprint-installed-reports"
```

Use the desired Python interpreter's absolute path if `python3` is not native. The new suite launches its own loopback panel on a random port and runs `tests/e2e_cache_dashboard.mjs` against that fixture URL; it never navigates the user's panel. The marketplace harness installs into a disposable Codex profile, compares source/installed SHA-256 values and runs the installed tests. Only reports are retained; temporary trees, profiles, browser data, databases and packages are removed.

## Results

- Test-first cache CLI acceptance: the initial seven cases failed before the runtime changes. The panel case failed before its UI changes; missing-parent and exclusion cases exposed the additional boundaries before their corrections.
- Final installed runtime regression: **110 passed, 0 failed** (99 existing cases and 11 new cache cases), with native FSEvents and ordinary-user permission checks, no skips. Includes marketplace install/hash checks, complete-baseline recovery, daily history, read-only panel and safe-upgrade fixtures.
- The final cache fixture isolation adjustment was reinstalled and checked separately: **11 passed, 0 failed**, with matching runtime/browser/test hashes and removed temporary profile. No runtime change followed the full regression.
- New cases cover independent readable baselines and measured growth; denied siblings; broad ancestor/parent-hook deduplication; nested denial; query-only retained metadata; historical-day isolation; bounded discovery/symlinks; old-parent retirement; permission recovery; missing parent; user exclusions; and all three cache-coverage panel views at 390 × 844 with no horizontal overflow or JavaScript exceptions.
- Read-only shallow metadata discovery on the personal Mac identified **14 named development-cache directories**, **9 EPERM gaps**, and **82 other readable application-cache directories outside the automatic development scope**. This probe did not traverse their contents, create baselines or update monitoring state.
- Static checks: `git diff --check`; manifest, package and runtime versions agree on 0.4.7. Unrelated source checkout remains clean.

## Acceptance boundary

This PR is a 0.4.7 candidate. The personal installation/service remains 0.4.6 until a separately authorized upgrade. Readable child baselines must actually finish after deployment; first measurements cannot establish earlier growth. Nested denied descendants can still make their own development-cache root partial. Protected directories remain uncovered, and daily partial evidence can remain for an earlier failure even after a later recovery. No claim of whole-cache readability, full-day coverage, visible native notifications or exclusive Codex ownership is made.

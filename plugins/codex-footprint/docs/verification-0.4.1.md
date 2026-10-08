# Version 0.4.1 resource regression acceptance — 2026-10-08

Version 0.4.0's features and responsive browser acceptance are documented in [0.4.0 acceptance](verification-0.4.0.md). Personal installation exposed an additional launchd boundary: a 256 soft descriptor limit made a 60-root native stream fail. The worker remained healthy on explicit polling fallback; it did not falsely report native monitoring.

Read-only native diagnosis with the same 60 existing roots succeeded at the shell's higher inherited limit, failed at 256, then succeeded with the corrected per-process soft allowance of 1,504. No user files/configuration/system resource limits were changed by this diagnosis. The correction raises only the worker soft limit within the inherited hard ceiling, capped at 8,192. Existing traversal cursor concurrency remains conservative.

Replay from WXY root on macOS, Python 3.14 and a compatible Codex CLI:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output /absolute/report-directory
```

Final installed-copy acceptance: **68 passed, 0 failed** (19 legacy, 15 global, 14 edges, 9 dashboard/service, 8 events/history/hooks, 3 safe-upgrade). The two additional real-worker cases create 60 independent temporary roots, inherit a 256 soft limit, and verify native event-driven external-growth detection. With both soft/hard limits fixed at 256, the other case verifies honest polling fallback and external-growth detection. Generated roots, processes, profiles and SQLite fixtures are removed; only replayable reports remain.

The first added test run used an invalid root configuration and therefore failed during setup; it was corrected rather than counted as proof of the native failure. A valid comparison against the installed 0.4.0 entry then failed specifically with `native_stream_creation_failed`; the corrected 0.4.1 installed copy passed. Reports record the runtime entry used for that comparison.

The visibility, native dropped-event fault-injection, first scheduled delivery and long-duration overhead limits in the 0.4.0 report still apply. Fixture success alone does not establish actual Codex UI visibility or whole-machine overhead.

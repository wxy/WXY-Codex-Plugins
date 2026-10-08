# WXY Codex Plugins distribution

As of **2026-10-08**, the canonical maintenance location is `WXY-Codex-Plugins/plugins/codex-footprint/`. It is a complete personal local Codex plugin, preserving lifecycle hooks and local MCP. Official-marketplace publication is outside current scope.

## Install from the shared marketplace

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
codex plugin add codex-footprint@wxy-codex-plugins
```

Skip the first command if that marketplace is already registered. For local development, the marketplace may point at the local WXY repository instead of the GitHub source; its entry resolves `./plugins/codex-footprint`. Install only this plugin. Existing Daydream and PR Title Hook entries are unchanged.

Installation, host hook trust and observation configuration are separate. Review/trust the hook definitions in a new Codex chat and set stable `CODEX_FOOTPRINT_DATA` and `CODEX_FOOTPRINT_CONFIG` paths shared by hooks and MCP. Configure explicit development roots. No configuration means inactive observation. V1 results appear through MCP in the conversation or through CLI JSON; a dedicated panel and reminders remain future work.

## Self-contained archive

From this plugin directory:

```sh
python3 scripts/codex_footprint.py package --output dist
```

The reproducible ZIP includes complete hooks, MCP, core, docs, tests and a small standalone `codex-footprint-local` catalog for testing/extracted archives. That nested convenience catalog does not replace the normal `wxy-codex-plugins` installation source. Git history, runtime state, artifacts and bytecode are excluded; a SHA-256 receipt is emitted beside the ZIP.

## Updates and evidence

Version 0.1.0 is the first WXY catalog entry. Bump the manifest, `pyproject.toml` and `src/codex_footprint/__init__.py` consistently when refreshing an installed version. Keep state outside versioned caches, and re-review changed hook definitions.

From the WXY repository root:

```sh
python3 plugins/codex-footprint/tests/e2e.py --output test-artifacts/codex-footprint/source
python3 tests/e2e_codex_footprint_marketplace.py --output test-artifacts/codex-footprint/marketplace
```

The marketplace E2E installs the actual WXY entry in a disposable Codex profile, compares source/installed hashes and runs the core E2E from the installed cache copy. It does not modify personal Codex settings or bypass hook trust. Real Desktop lifecycle delivery and observation overhead remain separate acceptance gates in `verification.md`.

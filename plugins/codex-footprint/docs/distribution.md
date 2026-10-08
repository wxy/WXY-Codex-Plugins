# WXY Codex Plugins distribution

Canonical source: `WXY-Codex-Plugins/plugins/codex-footprint/`. Version **0.4.1** packages the full local global-monitor and explicit-history runtime. Official-marketplace publication is outside scope.

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
codex plugin add codex-footprint@wxy-codex-plugins
```

Skip registration if present. The personal marketplace may point at the local WXY checkout; its entry resolves `./plugins/codex-footprint`. Install only this plugin; preserve Daydream and PR Title Hook. Installation, host hook trust and global observation enablement remain distinct. The same seven lifecycle events are retained. The guarded hook commands remain unchanged from 0.3.1. Version 0.4.1 adds public native file-event observation, seven-day charts and optional nonblocking active-chat context. The host may still request trust review according to its own rules. Do not bypass host trust. After upgrading, create a fresh chat to load new MCP tools, then globally enable once. See [configuration](configuration.md).

State stays outside version caches. For an existing installation, run the updated source helper:

```sh
python3 plugins/codex-footprint/scripts/update_plugin.py
```

It backs up the previous runtime temporarily, upgrades only this plugin, restores old chat hook entrypoints before returning and refreshes an existing stable runtime/service. Use this path for personal upgrades rather than a bare reinstall. Other installers can still purge old caches; guarded hooks stay nonblocking but may miss observations until the helper restores compatibility. Already-imported old MCP processes still need a fresh chat. Do not erase legacy databases or overwrite unrelated host configuration. The original independent repository remains provenance.

From the plugin directory:

```sh
python3 scripts/codex_footprint.py package --output dist
```

ZIPs retain full hooks, MCP, core, docs/tests and a standalone test catalog. Git/runtime state/artifacts/bytecode are excluded; reproducible metadata and a SHA-256 receipt are emitted. That catalog does not replace WXY's normal identity.

From WXY root:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output test-artifacts/codex-footprint/marketplace
```

The test installs the actual entry in a disposable Codex profile, compares hashes and runs all five E2E suites from the installed copy plus real-CLI safe-upgrade acceptance. It changes no personal profile, bypasses no trust and calls no model. Real Desktop event delivery, visible notifications and observation overhead remain distinct acceptance gates.

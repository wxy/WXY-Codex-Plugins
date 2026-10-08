# WXY Codex Plugins distribution

Canonical source: `WXY-Codex-Plugins/plugins/codex-footprint/`. Version **0.3.0** packages the full local global-monitor and explicit-history runtime. Official-marketplace publication is outside scope.

```sh
codex plugin marketplace add wxy/WXY-Codex-Plugins
codex plugin add codex-footprint@wxy-codex-plugins
```

Skip registration if present. The personal marketplace may point at the local WXY checkout; its entry resolves `./plugins/codex-footprint`. Install only this plugin; preserve Daydream and PR Title Hook. Installation, host hook trust and global observation enablement remain distinct. Seven hook definitions are unchanged from 0.1.0; do not bypass host trust. After upgrading, create a fresh chat to load new MCP tools, then globally enable once. See [configuration](configuration.md).

State stays outside version caches. Back up old version directories when running chats still reference them; a compatibility path may forward old hook entrypoints to the new installed runtime. Already-imported old MCP processes still need a fresh chat. Do not erase legacy databases or overwrite unrelated host configuration. The original independent repository remains provenance.

From the plugin directory:

```sh
python3 scripts/codex_footprint.py package --output dist
```

ZIPs retain full hooks, MCP, core, docs/tests and a standalone test catalog. Git/runtime state/artifacts/bytecode are excluded; reproducible metadata and a SHA-256 receipt are emitted. That catalog does not replace WXY's normal identity.

From WXY root:

```sh
python3 tests/e2e_codex_footprint_marketplace.py --output test-artifacts/codex-footprint/marketplace
```

The test installs the actual entry in a disposable Codex profile, compares hashes and runs all four E2E suites from the installed copy. It changes no personal profile, bypasses no trust and calls no model. Real Desktop event delivery, visible notifications and observation overhead remain distinct acceptance gates.

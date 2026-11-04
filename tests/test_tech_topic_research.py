from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/tech-topic-research"


class TechTopicResearchPackagingTests(unittest.TestCase):
    def test_marketplace_resolves_plugin_manifest(self) -> None:
        catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        entries = [entry for entry in catalog["plugins"] if entry["name"] == PLUGIN.name]
        self.assertEqual(len(entries), 1)
        source = entries[0]["source"]
        self.assertEqual(source["source"], "local")
        self.assertEqual((ROOT / source["path"]).resolve(), PLUGIN.resolve())
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        self.assertEqual(manifest["name"], entries[0]["name"])

    def test_manifest_discovers_the_complete_skill(self) -> None:
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        skills_root = (PLUGIN / manifest["skills"]).resolve()
        self.assertTrue(skills_root.is_relative_to(PLUGIN.resolve()))
        skills = list(skills_root.glob("*/SKILL.md"))
        self.assertEqual(len(skills), 1)
        self.assertEqual(skills[0].parent.name, PLUGIN.name)
        self.assertTrue((skills[0].parent / "agents/openai.yaml").is_file())
        self.assertEqual(manifest["version"], "0.1.0")

    def test_package_has_no_executable_components(self) -> None:
        files = {str(path.relative_to(PLUGIN)) for path in PLUGIN.rglob("*") if path.is_file()}
        self.assertEqual(files, {
            ".codex-plugin/plugin.json",
            "README.md",
            "skills/tech-topic-research/SKILL.md",
            "skills/tech-topic-research/agents/openai.yaml",
        })
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        self.assertFalse({"hooks", "mcpServers", "apps"}.intersection(manifest))


if __name__ == "__main__":
    unittest.main()

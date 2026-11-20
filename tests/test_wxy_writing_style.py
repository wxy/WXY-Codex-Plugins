import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins/wxy-writing-style"
SKILL = PLUGIN / "skills/wxy-writing-style"


class WritingStyleContract(unittest.TestCase):
    def test_standalone_catalog_registration(self):
        manifest = json.loads((PLUGIN / ".codex-plugin/plugin.json").read_text())
        catalog = json.loads((ROOT / ".agents/plugins/marketplace.json").read_text())
        entry, = [p for p in catalog["plugins"] if p["name"] == manifest["name"]]
        self.assertEqual(entry["source"]["path"], "./plugins/wxy-writing-style")
        self.assertEqual(manifest["skills"], "./skills/")
        self.assertTrue({"hooks", "mcpServers"}.isdisjoint(manifest))
        self.assertIn(f'版本：{manifest["version"]}', (SKILL / "SKILL.md").read_text())

    def test_modes_read_only_review_and_local_references(self):
        spec = (SKILL / "SKILL.md").read_text()
        self.assertIn("name: wxy-writing-style", spec)
        self.assertEqual(re.findall(r"^- \*\*\S+ / (draft|polish|review|adapt)\*\*", spec, re.M),
                         ["draft", "polish", "review", "adapt"])
        review = next(line for line in spec.splitlines() if "/ review**" in line)
        for fence in ("不写回", "不发布", "不输出整篇替稿"):
            self.assertIn(fence, review)
        for target in re.findall(r"\]\((references/[^)]*)\)", spec):
            self.assertTrue((SKILL / target).is_file(), target)

    def test_genres_and_corpus_scope(self):
        genres = (SKILL / "references/genres.md").read_text()
        self.assertEqual(re.findall(r"^## (.+?)（", genres, re.M),
                         ["评论", "采访", "短点评", "新闻", "技术介绍", "个人回顾"])
        corpus = (SKILL / "references/corpus.md").read_text()
        for boundary in ("文章下方评论", "包括作者自己的", "受访者回答", "私人稿件", "不收录"):
            self.assertIn(boundary, corpus)


if __name__ == "__main__":
    unittest.main()

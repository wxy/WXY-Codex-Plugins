import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).parents[1] / "plugins" / "codex-pr-title-hook" / "scripts" / "pr_title_after_pull_request.py"
SPEC = importlib.util.spec_from_file_location("pr_title_after_pull_request", SCRIPT)
HOOK = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(HOOK)


def event(**overrides):
    value = {
        "session_id": "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f",
        "turn_id": "turn-12345678",
        "hook_event_name": "PostToolUse",
        "tool_name": "mcp__codex_app__attach_artifact",
        "tool_input": {
            "artifact_type": "pull_request",
            "url": "https://github.com/wxy/ai-pulse-macos/pull/83",
        },
        "tool_response": {"isError": False},
    }
    value.update(overrides)
    return value


class PullRequestEventTests(unittest.TestCase):
    def test_accepts_successful_pull_request_attachment(self):
        self.assertEqual(
            HOOK.attached_pull_request(event()),
            (
                "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f",
                "https://github.com/wxy/ai-pulse-macos/pull/83",
            ),
        )

    def test_normalizes_trailing_slash_for_unique_counting(self):
        value = event()
        value["tool_input"]["url"] += "/"
        self.assertEqual(HOOK.attached_pull_request(value)[1], value["tool_input"]["url"].rstrip("/"))

    def test_rejects_failed_tool_response(self):
        self.assertIsNone(HOOK.attached_pull_request(event(tool_response={"isError": True})))

    def test_rejects_non_github_url(self):
        value = event()
        value["tool_input"]["url"] = "https://example.com/wxy/repo/pull/83"
        self.assertIsNone(HOOK.attached_pull_request(value))


class HistorySyncTests(unittest.TestCase):
    def history_thread(self):
        return {
            "name": "修复仪表盘缓存",
            "turns": [
                {
                    "items": [
                        {
                            "type": "mcpToolCall",
                            "server": "codex_app",
                            "tool": "attach_artifact",
                            "status": "completed",
                            "arguments": {
                                "artifact_type": "pull_request",
                                "url": "https://github.com/wxy/repo/pull/2/",
                            },
                            "result": {},
                            "error": None,
                        },
                        {
                            "type": "mcpToolCall",
                            "server": "codex_app",
                            "tool": "attach_artifact",
                            "status": "completed",
                            "arguments": json.dumps(
                                {
                                    "artifact_type": "pull_request",
                                    "url": "https://github.com/wxy/repo/pull/1",
                                }
                            ),
                            "result": {},
                            "error": None,
                        },
                        {
                            "type": "mcpToolCall",
                            "server": "codex_app",
                            "tool": "attach_artifact",
                            "status": "failed",
                            "arguments": {
                                "artifact_type": "pull_request",
                                "url": "https://github.com/wxy/repo/pull/99",
                            },
                            "error": "failed",
                        },
                    ]
                }
            ],
        }

    def test_matches_only_the_explicit_sync_phrase(self):
        self.assertTrue(
            HOOK.is_history_sync_prompt(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "  请使用 PR 信息更新会话标题  ",
                }
            )
        )
        self.assertFalse(
            HOOK.is_history_sync_prompt(
                {"hook_event_name": "UserPromptSubmit", "prompt": "请更新会话标题"}
            )
        )

    def test_matches_plugin_mention_with_short_command(self):
        self.assertTrue(
            HOOK.is_history_sync_prompt(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": (
                        "[@PR Title Hook]"
                        "(plugin://codex-pr-title-hook@codex-pr-title-hook-local) 修改标题"
                    ),
                }
            )
        )
        self.assertFalse(
            HOOK.is_history_sync_prompt(
                {"hook_event_name": "UserPromptSubmit", "prompt": "修改标题"}
            )
        )
        self.assertFalse(
            HOOK.is_history_sync_prompt(
                {
                    "hook_event_name": "UserPromptSubmit",
                    "prompt": "[@Other](plugin://other@personal) 修改标题",
                }
            )
        )

    def test_extracts_successful_unique_historical_prs(self):
        self.assertEqual(
            HOOK.historical_pull_request_urls(self.history_thread()),
            [
                "https://github.com/wxy/repo/pull/1",
                "https://github.com/wxy/repo/pull/2",
            ],
        )

    def test_explicit_prompt_syncs_state_and_title(self):
        fake_thread = self.history_thread()

        class FakeClient:
            title = None

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read_thread(self, _session_id, include_turns=False):
                self.assert_include_turns = include_turns
                return fake_thread

            def set_thread_title(self, _session_id, title):
                FakeClient.title = title

        with tempfile.TemporaryDirectory() as data_dir:
            with patch.dict(os.environ, {"CODEX_PR_TITLE_HOOK_DATA": data_dir}):
                with patch.object(HOOK, "AppServerClient", FakeClient):
                    message = HOOK.handle_event(
                        {
                            "session_id": "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f",
                            "turn_id": "sync-turn",
                            "hook_event_name": "UserPromptSubmit",
                            "prompt": HOOK.HISTORY_SYNC_PROMPT,
                        },
                        now=100.0,
                    )
            state = json.loads(
                (Path(data_dir) / "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f.json").read_text()
            )
        self.assertEqual(len(state["pr_urls"]), 2)
        self.assertEqual(state["active_turn_id"], "sync-turn")
        self.assertEqual(FakeClient.title, "⌛🔀🔀 修复仪表盘缓存")
        self.assertIn("同步 2 个唯一 PR", message)
        self.assertIn("不会反推", message)


class TimeTrackingTests(unittest.TestCase):
    def test_counts_agent_turn_time(self):
        state = HOOK.fresh_state()
        HOOK.begin_turn(state, "turn-a", 100.0)
        self.assertEqual(HOOK.projected_active_seconds(state, 160.0), 60.0)
        HOOK.finish_turn(state, "turn-a", 220.0)
        self.assertEqual(state["active_seconds"], 120.0)

    def test_does_not_finish_a_different_turn(self):
        state = HOOK.fresh_state()
        HOOK.begin_turn(state, "turn-a", 100.0)
        HOOK.finish_turn(state, "turn-b", 220.0)
        self.assertEqual(state["active_seconds"], 0.0)
        self.assertEqual(state["active_turn_id"], "turn-a")

    def test_new_prompt_discards_unclosed_interval(self):
        state = HOOK.fresh_state()
        HOOK.begin_turn(state, "turn-a", 100.0)
        HOOK.begin_turn(state, "turn-b", 1_000.0)
        self.assertEqual(state["active_seconds"], 0.0)
        self.assertEqual(state["active_turn_id"], "turn-b")

    def test_formats_compact_duration(self):
        self.assertEqual(HOOK.format_duration(1), "1m")
        self.assertEqual(HOOK.format_duration(3_600), "1h")
        self.assertEqual(HOOK.format_duration(4_800), "1h20m")


class TitleTests(unittest.TestCase):
    def test_places_metrics_before_summary(self):
        self.assertEqual(
            HOOK.compose_title("修复仪表盘缓存", 2, 4_800),
            "⏱️⌛🔀🔀 修复仪表盘缓存",
        )

    def test_adds_fork_symbol_at_threshold(self):
        self.assertEqual(
            HOOK.compose_title("修复仪表盘缓存", 3, 3 * 60 * 60),
            "⏱️⏱️⏱️🔀🔀🔀🌿 修复仪表盘缓存",
        )

    def test_time_threshold_also_adds_fork_symbol(self):
        self.assertIn("🌿 ", HOOK.compose_title("Long task", 1, 3 * 60 * 60))

    def test_uses_hourglass_before_one_hour(self):
        self.assertEqual(HOOK.time_badge(20 * 60), "⌛")

    def test_repeats_large_badge_counts_as_a_visual_nudge(self):
        self.assertEqual(HOOK.time_badge(5 * 60 * 60), "⏱️⏱️⏱️⏱️⏱️")
        self.assertEqual(HOOK.pr_badge(7), "🔀🔀🔀🔀🔀🔀🔀")

    def test_limits_display_width_and_preserves_metrics(self):
        title = HOOK.compose_title("很长的会话概括" * 20, 3, 12_345)
        self.assertLessEqual(HOOK.display_width(title), HOOK.TITLE_DISPLAY_LIMIT)
        self.assertTrue(title.startswith("⏱️⏱️⏱️⌛🔀🔀🔀🌿 "))
        self.assertTrue(title.endswith("…"))

    def test_recovers_summary_from_managed_prefix(self):
        self.assertEqual(
            HOOK.derive_base_title({"name": "⏱1h20m · PR×2 — 修复仪表盘缓存"}),
            "修复仪表盘缓存",
        )

    def test_recovers_summary_from_badge_prefix(self):
        self.assertEqual(
            HOOK.derive_base_title({"name": "⏱️⏱️⏱️🔀🔀🔀🌿 修复仪表盘缓存"}),
            "修复仪表盘缓存",
        )

    def test_recovers_summary_from_spaced_badge_prefix(self):
        self.assertEqual(
            HOOK.derive_base_title({"name": "⏱️⏱️⏱️ 🔀🔀🔀 🌿 修复仪表盘缓存"}),
            "修复仪表盘缓存",
        )

    def test_does_not_use_legacy_pr_title_as_summary(self):
        self.assertEqual(
            HOOK.derive_base_title(
                {"name": "PR #83 · Close release", "preview": "修复仪表盘缓存并验证刷新行为"}
            ),
            "修复仪表盘缓存并验证刷新行为",
        )

    def test_split_message_explains_symbol_and_choice(self):
        message = HOOK.split_message(3, 10_800)
        self.assertIn("🌿", message)
        self.assertIn("分叉", message)
        self.assertIn("新建任务", message)


class HookOutputTests(unittest.TestCase):
    def test_stop_always_returns_valid_json_shape(self):
        self.assertEqual(
            HOOK.hook_output({"hook_event_name": "Stop"}, None),
            {"continue": True},
        )

    def test_post_tool_use_only_outputs_when_there_is_a_message(self):
        self.assertIsNone(HOOK.hook_output({"hook_event_name": "PostToolUse"}, None))
        self.assertEqual(
            HOOK.hook_output({"hook_event_name": "PostToolUse"}, "split"),
            {"systemMessage": "split"},
        )


if __name__ == "__main__":
    unittest.main()

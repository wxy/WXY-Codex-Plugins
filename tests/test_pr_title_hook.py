import importlib.util
from pathlib import Path
import unittest


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
            "⏱️⌛ 🔀🔀 修复仪表盘缓存",
        )

    def test_adds_fork_symbol_at_threshold(self):
        self.assertEqual(
            HOOK.compose_title("修复仪表盘缓存", 3, 3 * 60 * 60),
            "⏱️⏱️⏱️ 🔀🔀🔀 🌿 修复仪表盘缓存",
        )

    def test_time_threshold_also_adds_fork_symbol(self):
        self.assertIn(" 🌿 ", HOOK.compose_title("Long task", 1, 3 * 60 * 60))

    def test_uses_hourglass_before_one_hour(self):
        self.assertEqual(HOOK.time_badge(20 * 60), "⌛")

    def test_repeats_large_badge_counts_as_a_visual_nudge(self):
        self.assertEqual(HOOK.time_badge(5 * 60 * 60), "⏱️⏱️⏱️⏱️⏱️")
        self.assertEqual(HOOK.pr_badge(7), "🔀🔀🔀🔀🔀🔀🔀")

    def test_limits_display_width_and_preserves_metrics(self):
        title = HOOK.compose_title("很长的会话概括" * 20, 3, 12_345)
        self.assertLessEqual(HOOK.display_width(title), HOOK.TITLE_DISPLAY_LIMIT)
        self.assertTrue(title.startswith("⏱️⏱️⏱️⌛ 🔀🔀🔀 🌿 "))
        self.assertTrue(title.endswith("…"))

    def test_recovers_summary_from_managed_prefix(self):
        self.assertEqual(
            HOOK.derive_base_title({"name": "⏱1h20m · PR×2 — 修复仪表盘缓存"}),
            "修复仪表盘缓存",
        )

    def test_recovers_summary_from_badge_prefix(self):
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

import importlib.util
import io
import json
import os
from contextlib import redirect_stderr
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
                    "startedAt": 10.0,
                    "completedAt": 100.0,
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

    def test_matches_the_explicit_sync_phrase(self):
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
        mention = "[@PR Title Hook](plugin://codex-pr-title-hook@wxy-codex-plugins)"
        for prompt in (mention, f"{mention} 修改标题", f"{mention} 任意自然语言都可以"):
            with self.subTest(prompt=prompt):
                self.assertTrue(
                    HOOK.is_history_sync_prompt(
                        {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
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
                "https://github.com/wxy/repo/pull/2",
                "https://github.com/wxy/repo/pull/1",
            ],
        )

    def test_reconstructs_completed_turn_time_and_caps_each_turn(self):
        thread = {
            "turns": [
                {"startedAt": 100, "completedAt": 700},
                {"startedAt": 1_000, "completedAt": 1_000 + HOOK.MAX_TURN_SECONDS + 10},
                {"startedAt": 1_700_000_000_000, "completedAt": 1_700_000_600_000},
                {"startedAt": "2026-09-20T00:00:00Z", "completedAt": "2026-09-20T01:00:00Z"},
                {"startedAt": 500},
                {"startedAt": 900, "completedAt": 800},
            ]
        }
        self.assertEqual(
            HOOK.historical_active_seconds(thread),
            600 + HOOK.MAX_TURN_SECONDS + 600 + 3_600,
        )

    def test_preserves_last_attachment_order_when_deduplicating(self):
        self.assertEqual(
            HOOK.unique_pull_request_urls(
                [
                    "https://github.com/wxy/repo/pull/1",
                    "https://github.com/wxy/repo/pull/2",
                    "https://github.com/wxy/repo/pull/1/",
                ]
            ),
            [
                "https://github.com/wxy/repo/pull/2",
                "https://github.com/wxy/repo/pull/1",
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
                titles = {
                    "https://github.com/wxy/repo/pull/1": "Add live refresh",
                    "https://github.com/wxy/repo/pull/2": "Fix dashboard caching",
                }
                bodies = {url: f"Body for {title}" for url, title in titles.items()}
                with patch.object(HOOK, "AppServerClient", FakeClient), patch.object(
                    HOOK,
                    "pull_request_details",
                    side_effect=lambda url: {"title": titles[url], "body": bodies[url]},
                ):
                    effect = HOOK.handle_event(
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
        self.assertTrue(state["managed"])
        self.assertEqual(len(state["pr_titles"]), 2)
        self.assertEqual(len(state["pr_bodies"]), 2)
        self.assertEqual(state["active_turn_id"], "sync-turn")
        self.assertEqual(FakeClient.title, "🔀🔀 live refresh · dashboard caching")
        self.assertIn("同步 2 个唯一 PR", effect.message)
        self.assertIn("重新计算", effect.message)
        self.assertIn("使用 AI 更新当前任务标题", effect.additional_context)
        self.assertIn("Body for Add live refresh", effect.additional_context)


class TimeTrackingTests(unittest.TestCase):
    def test_existing_pr_state_migrates_to_managed(self):
        state = HOOK.normalized_state(
            {"pr_urls": ["https://github.com/wxy/repo/pull/1"]}
        )
        self.assertTrue(state["managed"])

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

    def test_reconciliation_replaces_stale_cached_facts(self):
        state = HOOK.fresh_state()
        state["pr_urls"] = ["https://github.com/wxy/repo/pull/99"]
        state["active_seconds"] = 99_999
        HOOK.reconcile_historical_facts(
            state,
            {
                "turns": [
                    {
                        "startedAt": 100,
                        "completedAt": 1_000,
                        "items": [],
                    }
                ]
            },
        )
        self.assertEqual(state["pr_urls"], [])
        self.assertEqual(state["active_seconds"], 900)


class TitleTests(unittest.TestCase):
    def test_builds_a_rolling_summary_from_recent_prs(self):
        state = HOOK.fresh_state()
        state["pr_urls"] = [
            "https://github.com/wxy/repo/pull/82",
            "https://github.com/wxy/repo/pull/83",
            "https://github.com/wxy/repo/pull/84",
        ]
        state["pr_titles"] = {
            state["pr_urls"][0]: "Clarify dashboard collection and sync timestamps",
            state["pr_urls"][1]: "Close out AI Pulse 2.0 release",
            state["pr_urls"][2]: "Refresh stale dashboard when reopened",
        }
        summary = HOOK.recent_pr_summary(state)
        self.assertEqual(
            summary,
            "Refresh stale dashboard… · AI Pulse 2.0 r…",
        )
        self.assertNotEqual(summary, state["pr_titles"][state["pr_urls"][-1]])

    def test_single_pr_is_not_copied_verbatim(self):
        state = HOOK.fresh_state()
        url = "https://github.com/wxy/repo/pull/84"
        state["pr_urls"] = [url]
        state["pr_titles"] = {url: "Fix dashboard caching"}
        self.assertEqual(HOOK.recent_pr_summary(state), "近期：dashboard caching")

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

    def test_omits_zero_and_sub_ten_minute_badges(self):
        self.assertEqual(HOOK.time_badge(0), "")
        self.assertEqual(HOOK.time_badge(599), "")
        self.assertEqual(HOOK.pr_badge(0), "")
        self.assertEqual(HOOK.compose_title("修复仪表盘缓存", 0, 0), "修复仪表盘缓存")

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

    def test_recovers_summary_from_single_metric_badges(self):
        self.assertEqual(HOOK.derive_base_title({"name": "⌛ 修复缓存"}), "修复缓存")
        self.assertEqual(HOOK.derive_base_title({"name": "🔀🔀 修复缓存"}), "修复缓存")

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

    def test_stop_retains_an_ai_rewritten_summary(self):
        state = HOOK.fresh_state()
        state["pr_urls"] = ["https://github.com/wxy/repo/pull/84"]
        state["base_title"] = "近期：stale dashboard refresh"
        state["last_managed_title"] = "🔀 近期：stale dashboard refresh"

        class FakeClient:
            title = None

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read_thread(self, _session_id):
                return {"name": "🔀 仪表盘时间与重开刷新"}

            def set_thread_title(self, _session_id, title):
                FakeClient.title = title

        with patch.object(HOOK, "AppServerClient", FakeClient):
            title, _effect = HOOK.update_managed_title("session-12345678", state, 100.0)
        self.assertEqual(title, "🔀 仪表盘时间与重开刷新")
        self.assertEqual(state["base_title"], "仪表盘时间与重开刷新")
        self.assertIsNone(FakeClient.title)

    def test_stop_removes_stale_badges_when_history_has_no_facts(self):
        state = HOOK.fresh_state()
        state["base_title"] = "旧概括"
        state["last_managed_title"] = "⌛🔀 旧概括"

        class FakeClient:
            title = None

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

            def read_thread(self, _session_id):
                return {"name": "⌛🔀 旧概括"}

            def set_thread_title(self, _session_id, title):
                FakeClient.title = title

        with patch.object(HOOK, "AppServerClient", FakeClient):
            title, _effect = HOOK.update_managed_title("session-12345678", state, 100.0)
        self.assertEqual(title, "旧概括")
        self.assertEqual(FakeClient.title, "旧概括")

    def test_session_start_reconciles_history_before_updating_title(self):
        fake_thread = {
            "name": "⌛🔀 旧概括",
            "turns": [
                {
                    "startedAt": 0,
                    "completedAt": 3_600,
                    "items": [],
                }
            ],
        }

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
            stale_state = HOOK.fresh_state()
            stale_state["managed"] = True
            stale_state["active_turn_id"] = "abandoned-turn"
            stale_state["turn_started_at"] = 100.0
            state_path = Path(data_dir) / "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f.json"
            state_path.write_text(json.dumps(stale_state), encoding="utf-8")
            with patch.dict(os.environ, {"CODEX_PR_TITLE_HOOK_DATA": data_dir}), patch.object(
                HOOK, "AppServerClient", FakeClient
            ):
                HOOK.handle_event(
                    {
                        "session_id": "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f",
                        "hook_event_name": "SessionStart",
                    },
                    now=4_000,
                )
            state = json.loads(state_path.read_text())
        self.assertEqual(state["active_seconds"], 3_600)
        self.assertEqual(state["pr_urls"], [])
        self.assertIsNone(state["active_turn_id"])
        self.assertIsNone(state["turn_started_at"])
        self.assertEqual(FakeClient.title, "⏱️ 旧概括")


class HookOutputTests(unittest.TestCase):
    def test_unrelated_prompt_and_stop_do_not_create_state_or_open_app_server(self):
        class ForbiddenClient:
            def __init__(self):
                raise AssertionError("unrelated task must not open App Server")

        session_id = "unmanaged-session-1234"
        with tempfile.TemporaryDirectory() as data_dir:
            with patch.dict(os.environ, {"CODEX_PR_TITLE_HOOK_DATA": data_dir}), patch.object(
                HOOK, "AppServerClient", ForbiddenClient
            ):
                self.assertIsNone(
                    HOOK.handle_event(
                        {
                            "session_id": session_id,
                            "turn_id": "turn-1",
                            "hook_event_name": "UserPromptSubmit",
                            "prompt": "继续处理别的任务",
                        },
                        now=100,
                    )
                )
                self.assertIsNone(
                    HOOK.handle_event(
                        {
                            "session_id": session_id,
                            "turn_id": "turn-1",
                            "hook_event_name": "Stop",
                        },
                        now=200,
                    )
                )
            self.assertFalse((Path(data_dir) / f"{session_id}.json").exists())

    def test_known_hook_errors_are_fail_open(self):
        with patch.object(HOOK.sys, "stdin", io.StringIO("not json")), redirect_stderr(
            io.StringIO()
        ):
            self.assertEqual(HOOK.main(), 0)

    def test_stop_always_returns_valid_json_shape(self):
        self.assertEqual(
            HOOK.hook_output({"hook_event_name": "Stop"}, None),
            {"continue": True},
        )

    def test_post_tool_use_only_outputs_when_there_is_a_message(self):
        self.assertIsNone(HOOK.hook_output({"hook_event_name": "PostToolUse"}, None))
        self.assertEqual(
            HOOK.hook_output(
                {"hook_event_name": "PostToolUse"}, HOOK.HookEffect(message="split")
            ),
            {"systemMessage": "split"},
        )

    def test_adds_ai_context_in_the_supported_hook_shape(self):
        self.assertEqual(
            HOOK.hook_output(
                {"hook_event_name": "PostToolUse"},
                HOOK.HookEffect(additional_context="summarize recent PRs"),
            ),
            {
                "hookSpecificOutput": {
                    "hookEventName": "PostToolUse",
                    "additionalContext": "summarize recent PRs",
                }
            },
        )


if __name__ == "__main__":
    unittest.main()

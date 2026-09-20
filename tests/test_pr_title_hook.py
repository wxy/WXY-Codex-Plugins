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
            HOOK.successful_pull_request_event(event()),
            (
                "01a0bc5c-260a-7842-b3ef-5bb8519f2e8f",
                "https://github.com/wxy/ai-pulse-macos/pull/83",
            ),
        )

    def test_rejects_failed_tool_response(self):
        self.assertIsNone(
            HOOK.successful_pull_request_event(event(tool_response={"isError": True}))
        )

    def test_rejects_non_github_url(self):
        value = event()
        value["tool_input"]["url"] = "https://example.com/wxy/repo/pull/83"
        self.assertIsNone(HOOK.successful_pull_request_event(value))

    def test_rejects_non_pull_request_artifact(self):
        value = event()
        value["tool_input"]["artifact_type"] = "issue"
        self.assertIsNone(HOOK.successful_pull_request_event(value))


class TitleTests(unittest.TestCase):
    def test_formats_title(self):
        self.assertEqual(
            HOOK.normalized_title(83, " Close   out AI Pulse 2.0 release "),
            "PR #83 · Close out AI Pulse 2.0 release",
        )

    def test_limits_title_length(self):
        title = HOOK.normalized_title(123, "x" * 200)
        self.assertEqual(len(title), HOOK.TITLE_LIMIT)
        self.assertTrue(title.endswith("…"))


if __name__ == "__main__":
    unittest.main()

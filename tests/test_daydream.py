from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/codex-daydream/skills/codex-daydream/scripts/collect_daydream.py"
MARKER = "<!-- codex-daydream-checkpoint -->"
NEW_MARKER = "<!-- codex-daydream-output -->"


def event(event_type: str, timestamp: str, payload: dict) -> dict:
    return {"type": event_type, "timestamp": timestamp, "payload": payload}


def message(timestamp: str, role: str, text: str, phase: str | None = None) -> dict:
    payload = {
        "type": "message",
        "role": role,
        "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
    }
    if phase is not None:
        payload["phase"] = phase
    return event("response_item", timestamp, payload)


class DaydreamCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        (self.home / "sessions/2026/09/22").mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_session(self, name: str, rows: list[dict], archived: bool = False) -> None:
        root = self.home / ("archived_sessions" if archived else "sessions/2026/09/22")
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{name}.jsonl"
        path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def session_rows(self, session_id: str, created: str, *rows: dict, parent: str | None = None) -> list[dict]:
        payload = {"id": session_id, "timestamp": created, "cwd": "/Users/alice/SecretProject"}
        if parent:
            payload["parent_thread_id"] = parent
        return [event("session_meta", created, payload), *rows]

    def collect(self, *extra: str) -> dict:
        command = [
            sys.executable,
            str(SCRIPT),
            "--codex-home",
            str(self.home),
            "collect",
            "--now",
            "2026-09-22T23:00:00Z",
            "--timezone",
            "UTC",
            *extra,
        ]
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_collects_today_user_and_final_answer(self) -> None:
        self.write_session(
            "one",
            self.session_rows(
                "session-one",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T08:01:00Z", "user", "Repair the export pipeline"),
                message("2026-09-22T08:02:00Z", "assistant", "The export now passes tests.", "final_answer"),
                message("2026-09-22T08:01:30Z", "assistant", "I am inspecting files.", "commentary"),
            ),
        )
        result = self.collect()
        self.assertEqual(result["effective_scope"], "continuous-work-period")
        self.assertEqual(result["poster_meta"]["title"], "我与 Codex 工作的一天")
        self.assertEqual(result["poster_meta"]["title_en"], "A Day Working with Codex")
        self.assertEqual(result["poster_meta"]["purpose"], "今日在 Codex 中完成的工作成果")
        self.assertEqual(result["poster_meta"]["date"], "2026.09.22")
        self.assertEqual(result["poster_meta"]["creator"], "Xingyu Wang")
        self.assertEqual(result["poster_meta"]["source"], "Created with Codex Daydream")
        self.assertEqual(
            result["poster_meta"]["repository_url"],
            "https://github.com/wxy/WXY-Codex-Plugins",
        )
        self.assertNotIn("qr_target", result["poster_meta"])
        self.assertEqual(result["counts"]["tasks"], 1)
        texts = [item["text"] for item in result["tasks"][0]["messages"]]
        self.assertEqual(texts, ["Repair the export pipeline", "The export now passes tests."])

    def test_repeat_generation_keeps_earlier_work_and_excludes_old_poster(self) -> None:
        self.write_session(
            "checkpoint",
            self.session_rows(
                "session-checkpoint",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T18:10:00Z", "user", "Build storage cleanup workflow"),
                message("2026-09-22T19:00:00Z", "assistant", "Poster generated " + MARKER, "final_answer"),
                message("2026-09-22T20:00:00Z", "user", "Verify the cleanup workflow"),
                message("2026-09-22T20:30:00Z", "assistant", "Another poster " + NEW_MARKER, "final_answer"),
            ),
        )
        result = self.collect()
        texts = [item["text"] for item in result["tasks"][0]["messages"]]
        self.assertEqual(texts, ["Build storage cleanup workflow", "Verify the cleanup workflow"])
        self.assertEqual(result["window"]["start"], "2026-09-22T18:10+00:00")

    def test_cross_midnight_continuous_work(self) -> None:
        self.write_session(
            "overnight",
            self.session_rows(
                "session-overnight",
                "2026-09-22T12:00:00Z",
                message("2026-09-22T12:10:00Z", "user", "Start release work"),
                message("2026-09-22T23:30:00Z", "assistant", "Release review completed", "final_answer"),
                message("2026-09-23T02:50:00Z", "user", "Finish monitoring fixes"),
            ),
        )
        result = self.collect("--now", "2026-09-23T03:00:00Z")
        texts = [item["text"] for item in result["tasks"][0]["messages"]]
        self.assertEqual(texts, ["Release review completed", "Finish monitoring fixes"])
        self.assertEqual(result["poster_meta"]["date"], "2026.09.22–2026.09.23")

    def test_continuous_work_across_midnight_without_long_gap(self) -> None:
        self.write_session(
            "overnight-all",
            self.session_rows(
                "session-overnight-all",
                "2026-09-22T12:00:00Z",
                message("2026-09-22T12:10:00Z", "user", "Start storage work"),
                message("2026-09-22T17:00:00Z", "assistant", "Storage work progresses", "final_answer"),
                message("2026-09-22T22:00:00Z", "user", "Start release work"),
                message("2026-09-23T02:50:00Z", "assistant", "Release work verified", "final_answer"),
            ),
        )
        result = self.collect("--now", "2026-09-23T03:00:00Z")
        self.assertEqual(result["counts"]["messages"], 4)
        self.assertEqual(result["window"]["start"], "2026-09-22T12:10+00:00")

    def test_tool_timestamps_bridge_long_work_without_exposing_payload(self) -> None:
        self.write_session(
            "tool-work",
            self.session_rows(
                "session-tool-work",
                "2026-09-22T12:00:00Z",
                message("2026-09-22T12:10:00Z", "user", "Start monitoring work"),
                event("response_item", "2026-09-22T17:00:00Z", {"type": "function_call", "arguments": "private tool payload"}),
                event("response_item", "2026-09-22T22:00:00Z", {"type": "function_call_output", "output": "private result"}),
                message("2026-09-23T02:50:00Z", "assistant", "Monitoring fixes verified", "final_answer"),
            ),
        )
        result = self.collect("--now", "2026-09-23T03:00:00Z")
        self.assertEqual(result["window"]["start"], "2026-09-22T12:10+00:00")
        self.assertEqual(result["counts"]["messages"], 2)
        output = json.dumps(result)
        self.assertNotIn("private tool payload", output)
        self.assertNotIn("private result", output)

    def test_explicit_range_overrides_work_gap(self) -> None:
        self.write_session(
            "range",
            self.session_rows(
                "session-range",
                "2026-09-22T09:00:00Z",
                message("2026-09-22T09:10:00Z", "user", "Morning planning"),
                message("2026-09-22T19:00:00Z", "user", "Evening coding"),
            ),
        )
        result = self.collect("--start", "2026-09-22T09:00:00Z", "--end", "2026-09-22T20:00:00Z")
        self.assertEqual(result["effective_scope"], "explicit-range")
        self.assertEqual(result["counts"]["messages"], 2)

    def test_local_visual_candidates_are_opt_in(self) -> None:
        project = self.home / "project"
        project.mkdir()
        task = self.home / "task"
        task.mkdir()
        (project / "README.md").write_text("Storage app", encoding="utf-8")
        (project / "app-logo.svg").write_text("<svg/>", encoding="utf-8")
        self.write_session(
            "assets",
            [event("session_meta", "2026-09-22T18:00:00Z", {"id": "assets", "timestamp": "2026-09-22T18:00:00Z", "cwd": str(task)}),
             message("2026-09-22T18:10:00Z", "user", "Design app poster"),
             event("response_item", "2026-09-22T18:11:00Z", {"type": "function_call", "arguments": json.dumps({"workdir": str(project), "cmd": "inspect"})})],
        )
        self.assertNotIn(str(project), json.dumps(self.collect()))
        result = self.collect("--include-local-context")
        sources = next(item for item in result["local_project_sources"] if item["path"] == str(project))
        self.assertEqual(sources["readme_candidates"], [str(project / "README.md")])
        self.assertEqual(sources["visual_asset_candidates"], [str(project / "app-logo.svg")])

    def test_redacts_sensitive_strings_and_code(self) -> None:
        sensitive = (
            "Email alice@example.com path /Users/alice/SecretProject/file.swift "
            "token=ghp_abcdefghijklmnopqrstuvwxyz123456 and https://internal.example/x "
            "id 123e4567-e89b-12d3-a456-426614174000 ```swift\nprint(1)\n```"
        )
        self.write_session(
            "private",
            self.session_rows("private", "2026-09-22T08:00:00Z", message("2026-09-22T08:10:00Z", "user", sensitive)),
        )
        output = json.dumps(self.collect(), ensure_ascii=False)
        for secret in ("alice@example.com", "/Users/alice", "ghp_", "internal.example", "123e4567", "print(1)"):
            self.assertNotIn(secret, output)
        self.assertIn("<secret>", output)
        self.assertIn("<local-path>", output)
        self.assertIn("<code omitted>", output)

    def test_excludes_injected_context_and_subagents(self) -> None:
        self.write_session(
            "main",
            self.session_rows(
                "main",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T08:01:00Z", "user", "<environment_context>private</environment_context>"),
                message("2026-09-22T08:02:00Z", "user", "Visible request"),
            ),
        )
        self.write_session(
            "child",
            self.session_rows(
                "child",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T08:03:00Z", "user", "Subagent task"),
                parent="main",
            ),
        )
        messages = [item["text"] for task in self.collect()["tasks"] for item in task["messages"]]
        self.assertEqual(messages, ["Visible request"])

    def test_midnight_does_not_split_a_continuous_period(self) -> None:
        self.write_session(
            "days",
            self.session_rows(
                "days",
                "2026-09-21T08:00:00Z",
                message("2026-09-21T23:59:00Z", "user", "Yesterday"),
                message("2026-09-22T00:01:00Z", "user", "Today"),
            ),
        )
        output = json.dumps(self.collect(), ensure_ascii=False)
        self.assertIn("Today", output)
        self.assertIn("Yesterday", output)


if __name__ == "__main__":
    unittest.main()

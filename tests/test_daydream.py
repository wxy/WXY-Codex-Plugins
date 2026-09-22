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

    def collect(self, scope: str = "since-last", *extra: str) -> dict:
        command = [
            sys.executable,
            str(SCRIPT),
            "--codex-home",
            str(self.home),
            "collect",
            "--scope",
            scope,
            "--date",
            "2026-09-22",
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
        self.assertEqual(result["effective_scope"], "local-day")
        self.assertEqual(result["counts"]["tasks"], 1)
        texts = [item["text"] for item in result["tasks"][0]["messages"]]
        self.assertEqual(texts, ["Repair the export pipeline", "The export now passes tests."])

    def test_since_last_uses_latest_checkpoint(self) -> None:
        self.write_session(
            "checkpoint",
            self.session_rows(
                "session-checkpoint",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T08:10:00Z", "user", "Old work"),
                message("2026-09-22T09:00:00Z", "assistant", MARKER, "final_answer"),
                message("2026-09-22T10:00:00Z", "user", "New work"),
            ),
        )
        result = self.collect()
        self.assertTrue(result["window"]["checkpoint_found"])
        self.assertEqual(result["effective_scope"], "since-last-checkpoint")
        self.assertEqual(result["tasks"][0]["messages"][0]["text"], "New work")

    def test_today_scope_ignores_checkpoint(self) -> None:
        self.write_session(
            "today",
            self.session_rows(
                "session-today",
                "2026-09-22T08:00:00Z",
                message("2026-09-22T08:10:00Z", "user", "Morning work"),
                message("2026-09-22T09:00:00Z", "assistant", MARKER, "final_answer"),
            ),
        )
        result = self.collect("today")
        self.assertFalse(result["window"]["checkpoint_found"])
        self.assertEqual(result["tasks"][0]["messages"][0]["text"], "Morning work")

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
        output = json.dumps(self.collect(), ensure_ascii=False)
        self.assertIn("Visible request", output)
        self.assertNotIn("private", output)
        self.assertNotIn("Subagent task", output)

    def test_excludes_other_days(self) -> None:
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
        self.assertNotIn("Yesterday", output)


if __name__ == "__main__":
    unittest.main()

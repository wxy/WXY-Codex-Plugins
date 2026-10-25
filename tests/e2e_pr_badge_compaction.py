#!/usr/bin/env python3
"""Black-box E2E coverage for PR badge compaction through the hook CLI."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any


SESSION_ID = "e2e-pr-badge-session"
TURN_ID = "e2e-pr-badge-turn"
BASE_TITLE = "Compact PR badge"


FAKE_CODEX = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

log_path = Path(os.environ["FAKE_CODEX_LOG"])
thread_name = os.environ["FAKE_THREAD_NAME"]

for raw_line in sys.stdin:
    message = json.loads(raw_line)
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        print(json.dumps({"id": request_id, "result": {}}), flush=True)
    elif method == "initialized":
        continue
    elif method == "thread/read":
        print(
            json.dumps(
                {
                    "id": request_id,
                    "result": {
                        "thread": {
                            "id": message["params"]["threadId"],
                            "name": thread_name,
                            "turns": [],
                        }
                    },
                }
            ),
            flush=True,
        )
    elif method == "thread/name/set":
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(message["params"], ensure_ascii=False) + "\n")
        print(json.dumps({"id": request_id, "result": {}}), flush=True)
    else:
        print(json.dumps({"id": request_id, "result": {}}), flush=True)
'''


def state_for(
    pr_count: int, active_seconds: float, last_managed_title: str | None = None
) -> dict[str, Any]:
    urls = [f"https://github.com/example/repo/pull/{index}" for index in range(1, pr_count + 1)]
    return {
        "version": 4,
        "managed": True,
        "base_title": BASE_TITLE,
        "pr_urls": urls,
        "pr_titles": {},
        "pr_bodies": {},
        "last_managed_title": last_managed_title,
        "active_seconds": active_seconds,
        "active_turn_id": None,
        "turn_started_at": None,
        "split_notified": False,
    }


def severity_badge(count: int, low: str, medium: str, high: str) -> str:
    if count >= 25:
        return high
    if count >= 5:
        return medium
    if count >= 1:
        return low
    return ""


def expected_title(
    pr_count: int, active_seconds: float = 0.0, base_title: str = BASE_TITLE
) -> str:
    if active_seconds >= 25 * 3_600:
        time_prefix = "🕰️"
    elif active_seconds >= 5 * 3_600:
        time_prefix = "⏰"
    elif active_seconds >= 3_600:
        time_prefix = "⏱️"
    elif active_seconds >= 10 * 60:
        time_prefix = "⌛"
    else:
        time_prefix = ""
    prefix = time_prefix + severity_badge(pr_count, "🔀", "🌿", "🌳")
    return f"{prefix} {base_title}" if prefix else base_title


def run_case(
    hook_script: Path,
    fake_codex: Path,
    root: Path,
    pr_count: int,
    active_seconds: float = 0.0,
    current_name: str = BASE_TITLE,
    last_managed_title: str | None = None,
    expected_base_title: str = BASE_TITLE,
) -> dict[str, Any]:
    case_root = root / f"pr-{pr_count}-{len(list(root.iterdir()))}"
    data_root = case_root / "data"
    data_root.mkdir(parents=True)
    log_path = case_root / "app-server-requests.jsonl"
    state_path = data_root / f"{SESSION_ID}.json"
    state_path.write_text(
        json.dumps(state_for(pr_count, active_seconds, last_managed_title), ensure_ascii=False),
        encoding="utf-8",
    )
    event = {
        "session_id": SESSION_ID,
        "turn_id": TURN_ID,
        "hook_event_name": "Stop",
    }
    environment = os.environ.copy()
    environment.update(
        {
            "CODEX_PR_TITLE_HOOK_CODEX": str(fake_codex),
            "CODEX_PR_TITLE_HOOK_DATA": str(data_root),
            "FAKE_CODEX_LOG": str(log_path),
            "FAKE_THREAD_NAME": current_name,
        }
    )
    completed = subprocess.run(
        [sys.executable, str(hook_script)],
        input=json.dumps(event),
        text=True,
        capture_output=True,
        env=environment,
        timeout=15,
        check=False,
    )
    requests = []
    if log_path.is_file():
        requests = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    expected = expected_title(pr_count, active_seconds, expected_base_title)
    actual = requests[-1]["name"] if requests else current_name
    passed = (
        completed.returncode == 0
        and json.loads(completed.stdout) == {"continue": True}
        and actual == expected
        and sum(actual.count(symbol) for symbol in ("🔀", "🌿", "🌳")) <= 1
        and sum(actual.count(symbol) for symbol in ("⌛", "⏱", "⏰", "🕰")) <= 1
        and len(actual) <= 60
    )
    return {
        "pr_count": pr_count,
        "active_seconds": active_seconds,
        "current_name": current_name,
        "expected_title": expected,
        "actual_title": actual,
        "set_title_calls": len(requests),
        "returncode": completed.returncode,
        "stderr": completed.stderr.strip(),
        "passed": passed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--hook", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="pr-title-hook-e2e-") as temporary:
        root = Path(temporary)
        fake_codex = root / "fake-codex"
        fake_codex.write_text(FAKE_CODEX, encoding="utf-8")
        fake_codex.chmod(0o755)
        cases = [
            run_case(args.hook, fake_codex, root, count)
            for count in (0, 4, 5, 7, 12, 24, 25, 32, 100, 10_000)
        ]
        cases.extend(
            run_case(args.hook, fake_codex, root, 0, active_seconds=hours * 3_600 + remainder)
            for hours, remainder in (
                (4, 0),
                (5, 0),
                (7, 20 * 60),
                (24, 0),
                (25, 0),
                (32, 20 * 60),
                (100, 0),
                (10_000, 0),
            )
        )
        cases.append(
            run_case(
                args.hook,
                fake_codex,
                root,
                32,
                active_seconds=32 * 3_600 + 20 * 60,
                current_name="🕰️🌳 AI-refined summary",
                last_managed_title="🕰️⏰⏱️⏱️⌛🌳🌿🔀🔀 Older summary",
                expected_base_title="AI-refined summary",
            )
        )

    report = {
        "test": "PR and time severity badges through hook CLI and App Server protocol",
        "command": (
            "python3 tests/e2e_pr_badge_compaction.py "
            f"--hook {args.hook} --report {args.report}"
        ),
        "prerequisites": ["Python 3", "repository checkout"],
        "inputs": {
            "event": "Stop",
            "pr_counts": [0, 4, 5, 7, 12, 24, 25, 32, 100, 10000],
            "completed_hours": [0, 4, 5, 7, 24, 25, 32, 100, 10000],
            "severity_prefix_round_trip": True,
        },
        "results": cases,
        "passed": all(case["passed"] for case in cases),
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

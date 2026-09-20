#!/usr/bin/env python3
"""Rename the current Codex task after a GitHub pull request is attached."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import time
from typing import Any, TextIO
from urllib.parse import urlparse


ATTACH_TOOL = "mcp__codex_app__attach_artifact"
TITLE_LIMIT = 120
CLIENT_INFO = {
    "name": "pr_title_hook",
    "title": "PR Title Hook",
    "version": "1.0.0",
}


class HookError(RuntimeError):
    pass


def command_path(env_name: str, executable: str, fallbacks: tuple[str, ...]) -> str:
    override = os.environ.get(env_name)
    if override:
        return override
    discovered = shutil.which(executable)
    if discovered:
        return discovered
    for candidate in fallbacks:
        if Path(candidate).is_file():
            return candidate
    raise HookError(f"Could not find {executable}")


def pull_request_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    if not re.fullmatch(r"/[^/]+/[^/]+/pull/[1-9][0-9]*/?", parsed.path):
        return None
    return value


def successful_pull_request_event(event: Any) -> tuple[str, str] | None:
    if not isinstance(event, dict):
        return None
    if event.get("hook_event_name") != "PostToolUse" or event.get("tool_name") != ATTACH_TOOL:
        return None

    tool_input = event.get("tool_input")
    response = event.get("tool_response")
    if not isinstance(tool_input, dict) or tool_input.get("artifact_type") != "pull_request":
        return None
    if isinstance(response, dict) and response.get("isError") is True:
        return None

    session_id = event.get("session_id")
    url = pull_request_url(tool_input.get("url"))
    if not isinstance(session_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", session_id):
        return None
    if url is None:
        return None
    return session_id, url


def normalized_title(number: Any, title: Any) -> str:
    if not isinstance(number, int) or number < 1:
        raise HookError("GitHub returned an invalid pull request number")
    if not isinstance(title, str):
        raise HookError("GitHub returned an invalid pull request title")
    clean_title = " ".join(title.split())
    if not clean_title:
        raise HookError("GitHub returned an empty pull request title")

    prefix = f"PR #{number} · "
    available = TITLE_LIMIT - len(prefix)
    if len(clean_title) > available:
        clean_title = clean_title[: max(1, available - 1)].rstrip() + "…"
    return prefix + clean_title


def fetch_pull_request_title(url: str) -> str:
    gh = command_path(
        "CODEX_PR_TITLE_HOOK_GH",
        "gh",
        ("/opt/homebrew/bin/gh", "/usr/local/bin/gh"),
    )
    completed = subprocess.run(
        [gh, "pr", "view", url, "--json", "number,title"],
        check=False,
        capture_output=True,
        text=True,
        timeout=15,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or "unknown gh error"
        raise HookError(f"Could not read pull request metadata: {detail}")
    try:
        metadata = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        raise HookError("GitHub returned malformed pull request metadata") from error
    return normalized_title(metadata.get("number"), metadata.get("title"))


def send_json(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()


def wait_for_response(
    process: subprocess.Popen[str], selector: selectors.BaseSelector, request_id: int, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        events = selector.select(max(0.0, deadline - time.monotonic()))
        if not events:
            continue
        line = process.stdout.readline() if process.stdout is not None else ""
        if not line:
            break
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == request_id:
            return message
    raise HookError(f"Timed out waiting for app-server response {request_id}")


def set_thread_title(session_id: str, title: str) -> None:
    codex = command_path(
        "CODEX_PR_TITLE_HOOK_CODEX",
        "codex",
        (
            "/Applications/ChatGPT.app/Contents/Resources/codex",
            "/Applications/Codex.app/Contents/Resources/codex",
        ),
    )
    process = subprocess.Popen(
        [codex, "app-server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    if process.stdin is None or process.stdout is None:
        process.kill()
        raise HookError("Could not open app-server pipes")

    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    try:
        send_json(
            process.stdin,
            {"method": "initialize", "id": 0, "params": {"clientInfo": CLIENT_INFO}},
        )
        initialized = wait_for_response(process, selector, 0, 8)
        if "error" in initialized:
            raise HookError(f"Could not initialize app-server: {initialized['error']}")

        send_json(process.stdin, {"method": "initialized", "params": {}})
        send_json(
            process.stdin,
            {
                "method": "thread/name/set",
                "id": 1,
                "params": {"threadId": session_id, "name": title},
            },
        )
        renamed = wait_for_response(process, selector, 1, 8)
        if "error" in renamed:
            raise HookError(f"Could not rename Codex task: {renamed['error']}")
    finally:
        selector.close()
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        parsed = successful_pull_request_event(event)
        if parsed is None:
            return 0
        session_id, url = parsed
        title = fetch_pull_request_title(url)
        if "--dry-run" in sys.argv[1:]:
            print(title)
            return 0
        set_thread_title(session_id, title)
        return 0
    except (HookError, json.JSONDecodeError, OSError, subprocess.SubprocessError) as error:
        print(f"PR title hook: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

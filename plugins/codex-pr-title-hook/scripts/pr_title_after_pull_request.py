#!/usr/bin/env python3
"""Keep a Codex task title concise, descriptive, and fact-based."""

from __future__ import annotations

from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator, TextIO
import unicodedata
from urllib.parse import urlparse


ATTACH_TOOL = "mcp__codex_app__attach_artifact"
HISTORY_SYNC_PROMPT = "请使用 PR 信息更新会话标题"
PLUGIN_MENTION_SYNC = re.compile(
    r"^\[@[^\]]+\]\(plugin://codex-pr-title-hook(?:@[A-Za-z0-9_-]+)?\)\s+修改标题[。.!！]?$"
)
TITLE_DISPLAY_LIMIT = 60
SPLIT_PR_THRESHOLD = 3
SPLIT_ACTIVE_SECONDS = 3 * 60 * 60
MAX_TURN_SECONDS = 6 * 60 * 60
STATE_VERSION = 2
CLIENT_INFO = {
    "name": "pr_title_hook",
    "title": "PR Title Hook",
    "version": "2.0.0",
}
MANAGED_SUFFIX = re.compile(
    r"\s+·\s+\d+PR\s+·\s+\d+(?:h\d{2}m|h|m)(?:\s+·\s+可拆分)?$"
)
MANAGED_TEXT_PREFIX = re.compile(
    r"^⏱\d+(?:h\d{2}m|h|m)\s+·\s+PR×\d+(?:\s+·\s+⑂)?\s+—\s+"
)
MANAGED_BADGE_PREFIX = re.compile(
    r"^(?:(?:⏱️)+(?:⌛)?|⌛|⏱️×\d+)\s+(?:🔀+|🔀×\d+)(?:\s+🌿)?\s+"
)
LEGACY_PR_TITLE = re.compile(r"^PR\s+#\d+\s+·\s+", re.IGNORECASE)


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


def valid_session_id(value: Any) -> str | None:
    if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{8,128}", value):
        return value
    return None


def pull_request_url(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.hostname not in {"github.com", "www.github.com"}:
        return None
    if not re.fullmatch(r"/[^/]+/[^/]+/pull/[1-9][0-9]*/?", parsed.path):
        return None
    return value.rstrip("/")


def attached_pull_request(event: Any) -> tuple[str, str] | None:
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
    session_id = valid_session_id(event.get("session_id"))
    url = pull_request_url(tool_input.get("url"))
    if session_id is None or url is None:
        return None
    return session_id, url


def is_history_sync_prompt(event: Any) -> bool:
    if not isinstance(event, dict) or event.get("hook_event_name") != "UserPromptSubmit":
        return False
    prompt = event.get("prompt")
    if not isinstance(prompt, str):
        return False
    normalized = " ".join(prompt.split())
    return normalized == HISTORY_SYNC_PROMPT or PLUGIN_MENTION_SYNC.fullmatch(normalized) is not None


def historical_pull_request_urls(thread: Any) -> list[str]:
    if not isinstance(thread, dict):
        return []
    turns = thread.get("turns")
    if not isinstance(turns, list):
        return []
    urls: set[str] = set()
    for turn in turns:
        if not isinstance(turn, dict) or not isinstance(turn.get("items"), list):
            continue
        for item in turn["items"]:
            if not isinstance(item, dict) or item.get("type") != "mcpToolCall":
                continue
            if item.get("server") != "codex_app" or item.get("tool") != "attach_artifact":
                continue
            error = item.get("error")
            if item.get("status") != "completed" or (error is not None and error is not False):
                continue
            arguments = item.get("arguments")
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError:
                    continue
            if not isinstance(arguments, dict) or arguments.get("artifact_type") != "pull_request":
                continue
            result = item.get("result")
            if isinstance(result, dict) and result.get("isError") is True:
                continue
            url = pull_request_url(arguments.get("url"))
            if url is not None:
                urls.add(url)
    return sorted(urls)


def fresh_state() -> dict[str, Any]:
    return {
        "version": STATE_VERSION,
        "base_title": None,
        "pr_urls": [],
        "active_seconds": 0.0,
        "active_turn_id": None,
        "turn_started_at": None,
        "split_notified": False,
    }


def normalized_state(value: Any) -> dict[str, Any]:
    state = fresh_state()
    if not isinstance(value, dict):
        return state
    base_title = value.get("base_title")
    if isinstance(base_title, str) and base_title.strip():
        state["base_title"] = " ".join(base_title.split())
    urls = value.get("pr_urls")
    if isinstance(urls, list):
        state["pr_urls"] = sorted(
            {url for item in urls if (url := pull_request_url(item)) is not None}
        )
    active_seconds = value.get("active_seconds")
    if isinstance(active_seconds, (int, float)) and active_seconds >= 0:
        state["active_seconds"] = float(active_seconds)
    turn_id = value.get("active_turn_id")
    started_at = value.get("turn_started_at")
    if isinstance(turn_id, str) and isinstance(started_at, (int, float)) and started_at > 0:
        state["active_turn_id"] = turn_id
        state["turn_started_at"] = float(started_at)
    state["split_notified"] = value.get("split_notified") is True
    return state


def begin_turn(state: dict[str, Any], turn_id: Any, now: float) -> None:
    if not isinstance(turn_id, str) or not turn_id:
        return
    # If a previous Stop/Interrupt was missed, discard its open interval.
    # Counting idle time would be less truthful than under-counting that turn.
    state["active_turn_id"] = turn_id
    state["turn_started_at"] = now


def finish_turn(state: dict[str, Any], turn_id: Any, now: float) -> None:
    active_turn_id = state.get("active_turn_id")
    started_at = state.get("turn_started_at")
    if not isinstance(active_turn_id, str) or not isinstance(started_at, (int, float)):
        return
    if isinstance(turn_id, str) and turn_id and turn_id != active_turn_id:
        return
    elapsed = max(0.0, min(now - float(started_at), MAX_TURN_SECONDS))
    state["active_seconds"] = float(state.get("active_seconds", 0.0)) + elapsed
    state["active_turn_id"] = None
    state["turn_started_at"] = None


def projected_active_seconds(state: dict[str, Any], now: float) -> float:
    total = float(state.get("active_seconds", 0.0))
    started_at = state.get("turn_started_at")
    if isinstance(started_at, (int, float)):
        total += max(0.0, min(now - float(started_at), MAX_TURN_SECONDS))
    return total


def format_duration(seconds: float) -> str:
    minutes = max(1, int((max(0.0, seconds) + 30) // 60))
    if minutes < 60:
        return f"{minutes}m"
    hours, remainder = divmod(minutes, 60)
    if remainder == 0:
        return f"{hours}h"
    return f"{hours}h{remainder:02d}m"


def character_display_width(character: str) -> int:
    if character in {"\ufe0f", "\u200d"}:
        return 0
    return 2 if character == "⏱" or unicodedata.east_asian_width(character) in {"W", "F"} else 1


def display_width(value: str) -> int:
    return sum(character_display_width(character) for character in value)


def truncate_display(value: str, limit: int) -> str:
    clean = " ".join(value.split())
    if display_width(clean) <= limit:
        return clean
    if limit <= 1:
        return "…"[:limit]
    result: list[str] = []
    width = 0
    for character in clean:
        character_width = character_display_width(character)
        if width + character_width > limit - 1:
            break
        result.append(character)
        width += character_width
    return "".join(result).rstrip() + "…"


def should_suggest_split(pr_count: int, active_seconds: float) -> bool:
    return pr_count >= SPLIT_PR_THRESHOLD or active_seconds >= SPLIT_ACTIVE_SECONDS


def time_badge(active_seconds: float) -> str:
    seconds = max(0.0, active_seconds)
    whole_hours = int(seconds // 3_600)
    partial_hour = seconds - (whole_hours * 3_600) >= 10 * 60
    if whole_hours == 0:
        return "⌛"
    return ("⏱️" * whole_hours) + ("⌛" if partial_hour else "")


def pr_badge(pr_count: int) -> str:
    count = max(1, pr_count)
    return "🔀" * count


def compose_title(base_title: str, pr_count: int, active_seconds: float) -> str:
    badges = [time_badge(active_seconds), pr_badge(pr_count)]
    if should_suggest_split(pr_count, active_seconds):
        badges.append("🌿")
    prefix = " ".join(badges) + " "
    available = max(8, TITLE_DISPLAY_LIMIT - display_width(prefix))
    base = truncate_display(base_title, available)
    return prefix + base


def compact_preview(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    for raw_line in value.splitlines():
        line = raw_line.strip().lstrip("#").strip()
        if not line or line.startswith("{") or line.startswith("Referenced ChatGPT conversation"):
            continue
        line = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", line)
        line = re.sub(r"[`*_>]", "", line)
        clean = " ".join(line.split())
        if clean:
            return truncate_display(clean, 40)
    return None


def derive_base_title(thread: dict[str, Any]) -> str:
    name = thread.get("name")
    if isinstance(name, str):
        clean_name = " ".join(name.split())
        clean_name = MANAGED_BADGE_PREFIX.sub("", clean_name).strip()
        clean_name = MANAGED_TEXT_PREFIX.sub("", clean_name).strip()
        clean_name = MANAGED_SUFFIX.sub("", clean_name).strip()
        if clean_name and not LEGACY_PR_TITLE.match(clean_name):
            return clean_name
    return compact_preview(thread.get("preview")) or "Codex 任务"


def data_root() -> Path:
    value = os.environ.get("CODEX_PR_TITLE_HOOK_DATA") or os.environ.get("PLUGIN_DATA")
    if not value:
        raise HookError("PLUGIN_DATA is not available")
    root = Path(value).expanduser()
    root.mkdir(parents=True, exist_ok=True)
    return root


@contextmanager
def locked_state(session_id: str) -> Iterator[dict[str, Any]]:
    root = data_root()
    state_path = root / f"{session_id}.json"
    lock_path = root / f"{session_id}.lock"
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            if state_path.is_file():
                try:
                    state = normalized_state(json.loads(state_path.read_text(encoding="utf-8")))
                except (json.JSONDecodeError, OSError):
                    state = fresh_state()
            else:
                state = fresh_state()
            yield state
            state["version"] = STATE_VERSION
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=root, prefix=f"{session_id}.", suffix=".tmp", delete=False
            ) as temporary:
                json.dump(state, temporary, ensure_ascii=False, sort_keys=True)
                temporary.write("\n")
                temporary_path = Path(temporary.name)
            os.replace(temporary_path, state_path)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def send_json(stream: TextIO, payload: dict[str, Any]) -> None:
    stream.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    stream.flush()


class AppServerClient:
    def __init__(self) -> None:
        codex = command_path(
            "CODEX_PR_TITLE_HOOK_CODEX",
            "codex",
            (
                "/Applications/ChatGPT.app/Contents/Resources/codex",
                "/Applications/Codex.app/Contents/Resources/codex",
            ),
        )
        self.process = subprocess.Popen(
            [codex, "app-server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        if self.process.stdin is None or self.process.stdout is None:
            self.process.kill()
            raise HookError("Could not open app-server pipes")
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.next_request_id = 1
        send_json(
            self.process.stdin,
            {"method": "initialize", "id": 0, "params": {"clientInfo": CLIENT_INFO}},
        )
        initialized = self._wait_for_response(0, 8)
        if "error" in initialized:
            self.close()
            raise HookError(f"Could not initialize app-server: {initialized['error']}")
        send_json(self.process.stdin, {"method": "initialized", "params": {}})

    def _wait_for_response(self, request_id: int, timeout: float) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            events = self.selector.select(max(0.0, deadline - time.monotonic()))
            if not events:
                continue
            line = self.process.stdout.readline() if self.process.stdout is not None else ""
            if not line:
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                return message
        raise HookError(f"Timed out waiting for app-server response {request_id}")

    def request(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        request_id = self.next_request_id
        self.next_request_id += 1
        if self.process.stdin is None:
            raise HookError("app-server input is closed")
        send_json(self.process.stdin, {"method": method, "id": request_id, "params": params})
        response = self._wait_for_response(request_id, 8)
        if "error" in response:
            raise HookError(f"app-server {method} failed: {response['error']}")
        result = response.get("result")
        return result if isinstance(result, dict) else {}

    def read_thread(self, session_id: str, include_turns: bool = False) -> dict[str, Any]:
        result = self.request(
            "thread/read", {"threadId": session_id, "includeTurns": include_turns}
        )
        thread = result.get("thread")
        if not isinstance(thread, dict):
            raise HookError("app-server returned no thread")
        return thread

    def set_thread_title(self, session_id: str, title: str) -> None:
        self.request("thread/name/set", {"threadId": session_id, "name": title})

    def close(self) -> None:
        if getattr(self, "selector", None) is not None:
            self.selector.close()
        process = getattr(self, "process", None)
        if process is None:
            return
        if process.stdin is not None and not process.stdin.closed:
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

    def __enter__(self) -> "AppServerClient":
        return self

    def __exit__(self, _type: Any, _value: Any, _traceback: Any) -> None:
        self.close()


def split_message(pr_count: int, active_seconds: float) -> str:
    return (
        f"此任务已累计 {pr_count} 个 PR、约 {format_duration(active_seconds)} 的 Codex 工作时间。"
        "标题中的 🌿 表示可考虑拆分：若下一步仍是同一目标的并行方案，可以分叉；"
        "若目标已经变化，建议新建任务。"
    )


def sync_history_message(pr_count: int, added_count: int, split: bool) -> str:
    message = (
        f"已从当前任务的历史记录同步 {pr_count} 个唯一 PR"
        f"（本次新增 {added_count} 个），并更新会话标题。"
        "历史同步不会反推插件启用前的工作时间。"
    )
    if split:
        message += (
            "标题中的 🌿 表示可考虑拆分：同一目标的并行方案可以分叉；"
            "目标已经变化则建议新建任务。"
        )
    return message


def sync_historical_pull_requests(
    session_id: str, state: dict[str, Any], now: float
) -> str:
    with AppServerClient() as client:
        thread = client.read_thread(session_id, include_turns=True)
        historical_urls = historical_pull_request_urls(thread)
        if not historical_urls:
            return "未在当前 Codex 任务的已存储历史中找到成功附加的 PR；会话标题未更改。"
        previous_urls = set(state["pr_urls"])
        state["pr_urls"] = sorted(previous_urls | set(historical_urls))
        if not state.get("base_title"):
            state["base_title"] = derive_base_title(thread)
        active_seconds = projected_active_seconds(state, now)
        title = compose_title(str(state["base_title"]), len(state["pr_urls"]), active_seconds)
        if thread.get("name") != title:
            client.set_thread_title(session_id, title)
        split = should_suggest_split(len(state["pr_urls"]), active_seconds)
        if split:
            state["split_notified"] = True
        return sync_history_message(
            len(state["pr_urls"]), len(set(state["pr_urls"]) - previous_urls), split
        )


def update_managed_title(
    session_id: str, state: dict[str, Any], now: float
) -> tuple[str, str | None]:
    active_seconds = projected_active_seconds(state, now)
    pr_count = len(state["pr_urls"])
    with AppServerClient() as client:
        thread = client.read_thread(session_id)
        if not state.get("base_title"):
            state["base_title"] = derive_base_title(thread)
        title = compose_title(str(state["base_title"]), pr_count, active_seconds)
        if thread.get("name") != title:
            client.set_thread_title(session_id, title)
    message = None
    if should_suggest_split(pr_count, active_seconds) and not state.get("split_notified"):
        state["split_notified"] = True
        message = split_message(pr_count, active_seconds)
    return title, message


def handle_event(event: Any, now: float | None = None) -> str | None:
    if not isinstance(event, dict):
        return None
    session_id = valid_session_id(event.get("session_id"))
    if session_id is None:
        return None
    timestamp = time.time() if now is None else now
    event_name = event.get("hook_event_name")

    if event_name == "UserPromptSubmit":
        with locked_state(session_id) as state:
            begin_turn(state, event.get("turn_id"), timestamp)
            if is_history_sync_prompt(event):
                return sync_historical_pull_requests(session_id, state, timestamp)
        return None
    if event_name in {"Interrupt", "SessionEnd"}:
        with locked_state(session_id) as state:
            finish_turn(state, event.get("turn_id"), timestamp)
        return None
    if event_name == "Stop":
        with locked_state(session_id) as state:
            finish_turn(state, event.get("turn_id"), timestamp)
            if state["pr_urls"]:
                _, message = update_managed_title(session_id, state, timestamp)
                return message
        return None

    parsed = attached_pull_request(event)
    if parsed is None:
        return None
    _, url = parsed
    with locked_state(session_id) as state:
        state["pr_urls"] = sorted(set(state["pr_urls"]) | {url})
        _, message = update_managed_title(session_id, state, timestamp)
        return message


def hook_output(event: Any, message: str | None) -> dict[str, Any] | None:
    if not isinstance(event, dict):
        return None
    output: dict[str, Any] = {}
    if event.get("hook_event_name") == "Stop":
        output["continue"] = True
    if message:
        output["systemMessage"] = message
    return output or None


def main() -> int:
    try:
        event = json.load(sys.stdin)
        message = handle_event(event)
        output = hook_output(event, message)
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
        return 0
    except (HookError, json.JSONDecodeError, OSError, subprocess.SubprocessError) as error:
        print(f"PR title hook: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

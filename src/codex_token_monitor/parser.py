from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from .models import SessionStats, TokenUsage


class SessionLogError(RuntimeError):
    """Raised when a session log cannot provide token usage."""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _usage(value: Any) -> TokenUsage | None:
    return TokenUsage.from_mapping(value)


def _extract_cumulative(record: Mapping[str, Any]) -> tuple[TokenUsage, str] | None:
    """Extract known cumulative snapshots without relying on one CLI version."""

    payload = _mapping(record.get("payload"))
    record_type = record.get("type")

    if record_type == "token_usage_record":
        parsed = _usage(payload.get("thread_token_usage"))
        if parsed is not None:
            return parsed, "token_usage_record.thread_token_usage"

    if record_type == "event_msg" and payload.get("type") == "token_count":
        info = _mapping(payload.get("info"))
        parsed = _usage(info.get("total_token_usage"))
        if parsed is not None:
            return parsed, "event_msg.token_count.total_token_usage"

    return None


def _extract_incremental(record: Mapping[str, Any]) -> TokenUsage | None:
    """Extract a per-response value that is safe to add when no total exists."""

    payload = _mapping(record.get("payload"))
    if record.get("type") == "token_usage_record":
        return _usage(payload.get("usage"))

    # Fallbacks for API-style or older JSONL records. These are deliberately
    # narrow so message content containing token-like keys is not interpreted.
    for container in (record, payload):
        parsed = _usage(_mapping(container).get("usage"))
        if parsed is not None:
            return parsed
    return None


def parse_session(path: str | Path) -> SessionStats:
    session_path = Path(path).expanduser().resolve()
    latest: TokenUsage | None = None
    source = ""
    session_id: str | None = None
    cli_version: str | None = None
    context_window: int | None = None
    invalid_lines = 0
    incremental_total = TokenUsage()
    incremental_records = 0

    try:
        stream = session_path.open("r", encoding="utf-8-sig", errors="replace")
    except OSError as exc:
        raise SessionLogError(f"無法讀取 session log：{session_path}") from exc

    with stream:
        for raw_line in stream:
            if not raw_line.strip():
                continue
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                invalid_lines += 1
                continue
            if not isinstance(record, Mapping):
                continue

            payload = _mapping(record.get("payload"))
            if record.get("type") == "session_meta":
                session_id = str(payload.get("session_id") or payload.get("id") or "") or None
                cli_version = str(payload.get("cli_version") or "") or None
                raw_window = payload.get("context_window")
                if isinstance(raw_window, int) and not isinstance(raw_window, bool):
                    context_window = raw_window

            if record.get("type") == "event_msg" and payload.get("type") == "token_count":
                info = _mapping(payload.get("info"))
                raw_window = info.get("model_context_window")
                if isinstance(raw_window, int) and not isinstance(raw_window, bool):
                    context_window = raw_window

            candidate = _extract_cumulative(record)
            if candidate is not None:
                latest, source = candidate
            incremental = _extract_incremental(record)
            if incremental is not None:
                incremental_total += incremental
                incremental_records += 1

    if latest is None:
        if incremental_records:
            latest = incremental_total
            source = "summed_incremental_usage"
        else:
            raise SessionLogError(
                "session log 中找不到支援的 token usage 紀錄；"
                "此 Codex 版本可能尚未寫入 usage，或使用了未知格式。"
            )

    return SessionStats(
        path=str(session_path),
        usage=latest,
        source=source,
        session_id=session_id,
        cli_version=cli_version,
        context_window=context_window,
        invalid_lines=invalid_lines,
    )


def find_latest_session(sessions_dir: str | Path) -> Path:
    root = Path(sessions_dir).expanduser()
    if not root.is_dir():
        raise SessionLogError(f"找不到 Codex sessions 目錄：{root}")
    candidates = [path for path in root.rglob("*.jsonl") if path.is_file()]
    if not candidates:
        raise SessionLogError(f"sessions 目錄中沒有 JSONL 檔案：{root}")
    return max(candidates, key=lambda path: path.stat().st_mtime_ns)


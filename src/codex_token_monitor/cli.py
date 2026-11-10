from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Sequence

from .models import SessionStats, TokenUsage
from .parser import SessionLogError, find_latest_session, parse_session
from .state import StateStore, default_state_file


def default_sessions_dir() -> Path:
    codex_home = os.environ.get("CODEX_HOME")
    return Path(codex_home).expanduser() / "sessions" if codex_home else Path.home() / ".codex" / "sessions"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="codex-token-monitor",
        description="唯讀監控 Codex CLI session token 使用量。",
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--session", type=Path, help="指定一個 session JSONL 檔案")
    source.add_argument(
        "--sessions-dir",
        type=Path,
        default=default_sessions_dir(),
        help="Codex sessions 目錄（預設：%(default)s）",
    )
    parser.add_argument("--watch", action="store_true", help="持續監控直到按 Ctrl+C")
    parser.add_argument("--interval", type=float, default=2.0, help="監控間隔秒數（預設：2）")
    parser.add_argument("--state-file", type=Path, default=default_state_file(), help=argparse.SUPPRESS)
    parser.add_argument("--no-cache", action="store_true", help="不讀寫跨次執行的增量狀態")
    parser.add_argument("--json", action="store_true", help="輸出 JSON，方便其他工具使用")
    return parser


def _format_usage(prefix: str, usage: TokenUsage) -> list[str]:
    return [
        prefix,
        f"  輸入 Token（含快取） : {usage.input:>12,}",
        f"  快取 Token（輸入子集）: {usage.cached_input:>12,}",
        f"  輸出 Token            : {usage.output:>12,}",
        f"  總 Token              : {usage.total:>12,}",
    ]


def render_text(stats: SessionStats, increment: TokenUsage, reset: bool) -> str:
    lines = [
        "Codex Token Monitor",
        f"Session : {stats.session_id or Path(stats.path).stem}",
        f"檔案    : {stats.path}",
        f"格式來源: {stats.source}",
    ]
    if stats.cli_version:
        lines.append(f"CLI 版本: {stats.cli_version}")
    lines.extend(_format_usage("Session 累計", stats.usage))
    label = "本次增量（偵測到計數重設）" if reset else "自上次檢查增量"
    lines.extend(_format_usage(label, increment))
    if stats.invalid_lines:
        lines.append(f"警告：已略過 {stats.invalid_lines} 行無法解析的 JSON。")
    return "\n".join(lines)


def render_json(stats: SessionStats, increment: TokenUsage, reset: bool) -> str:
    return json.dumps(
        {
            "session": {
                "id": stats.session_id,
                "path": stats.path,
                "cli_version": stats.cli_version,
                "source": stats.source,
                "context_window": stats.context_window,
            },
            "usage": stats.usage.as_dict(),
            "increment": increment.as_dict(),
            "counter_reset": reset,
            "invalid_lines": stats.invalid_lines,
        },
        ensure_ascii=False,
    )


def _resolve_session(args: argparse.Namespace) -> Path:
    return args.session if args.session else find_latest_session(args.sessions_dir)


def _display_once(
    session_path: Path,
    previous: TokenUsage | None,
    as_json: bool,
) -> tuple[SessionStats, TokenUsage]:
    stats = parse_session(session_path)
    increment, reset = stats.usage.delta(previous)
    output = render_json(stats, increment, reset) if as_json else render_text(stats, increment, reset)
    print(output)
    return stats, stats.usage


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.interval <= 0:
        print("錯誤：--interval 必須大於 0。", file=sys.stderr)
        return 2

    store = None if args.no_cache else StateStore(args.state_file)
    try:
        session_path = _resolve_session(args).expanduser().resolve()
        previous = store.get(str(session_path)) if store else None

        while True:
            stats, previous = _display_once(session_path, previous, args.json)
            if store:
                store.put(stats.path, stats.usage)
            if not args.watch:
                return 0
            time.sleep(args.interval)
            if not args.json:
                print("\n" + "-" * 60)
    except KeyboardInterrupt:
        return 0
    except SessionLogError as exc:
        print(f"錯誤：{exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"錯誤：無法更新監控狀態：{exc}", file=sys.stderr)
        return 1


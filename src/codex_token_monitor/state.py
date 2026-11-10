from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from .models import TokenUsage


def default_state_file() -> Path:
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        base = Path(os.environ["LOCALAPPDATA"])
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "codex-token-monitor" / "state.json"


class StateStore:
    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"version": 1, "sessions": {}}
        if not isinstance(value, dict) or not isinstance(value.get("sessions"), dict):
            return {"version": 1, "sessions": {}}
        return value

    def get(self, session_path: str) -> TokenUsage | None:
        sessions = self._read()["sessions"]
        value = sessions.get(session_path)
        return TokenUsage.from_mapping(value) if isinstance(value, Mapping) else None

    def put(self, session_path: str, usage: TokenUsage) -> None:
        state = self._read()
        state["version"] = 1
        state["sessions"][session_path] = usage.as_dict()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(self.path)


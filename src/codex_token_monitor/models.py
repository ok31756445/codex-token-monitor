from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


def _non_negative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError, OverflowError):
        return 0


def _first(mapping: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in mapping and mapping[name] is not None:
            return mapping[name]
    return 0


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Normalized token counts.

    ``cached_input`` is a subset of ``input`` and must not be added to total.
    """

    input: int = 0
    output: int = 0
    cached_input: int = 0
    total: int = 0

    @classmethod
    def from_mapping(cls, value: Any) -> TokenUsage | None:
        if not isinstance(value, Mapping):
            return None

        input_tokens = _non_negative_int(
            _first(value, ("input_tokens", "prompt_tokens", "input"))
        )
        output_tokens = _non_negative_int(
            _first(value, ("output_tokens", "completion_tokens", "output"))
        )
        cached = _first(
            value,
            (
                "cached_input_tokens",
                "cached_tokens",
                "cache_read_input_tokens",
            ),
        )
        details = value.get("input_tokens_details")
        if not cached and isinstance(details, Mapping):
            cached = details.get("cached_tokens", 0)

        recognized = any(
            name in value
            for name in (
                "input_tokens",
                "prompt_tokens",
                "output_tokens",
                "completion_tokens",
                "total_tokens",
            )
        )
        if not recognized:
            return None

        total = _non_negative_int(value.get("total_tokens"))
        if not total:
            total = input_tokens + output_tokens
        return cls(
            input=input_tokens,
            output=output_tokens,
            cached_input=_non_negative_int(cached),
            total=total,
        )

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input=self.input + other.input,
            output=self.output + other.output,
            cached_input=self.cached_input + other.cached_input,
            total=self.total + other.total,
        )

    def delta(self, previous: TokenUsage | None) -> tuple[TokenUsage, bool]:
        """Return increment since ``previous`` and whether a reset was detected."""

        if previous is None:
            return self, False
        current = (self.input, self.output, self.cached_input, self.total)
        before = (
            previous.input,
            previous.output,
            previous.cached_input,
            previous.total,
        )
        if any(now < old for now, old in zip(current, before)):
            return self, True
        return (
            TokenUsage(
                input=self.input - previous.input,
                output=self.output - previous.output,
                cached_input=self.cached_input - previous.cached_input,
                total=self.total - previous.total,
            ),
            False,
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input,
            "output_tokens": self.output,
            "cached_input_tokens": self.cached_input,
            "total_tokens": self.total,
        }


@dataclass(frozen=True, slots=True)
class SessionStats:
    path: str
    usage: TokenUsage
    source: str
    session_id: str | None = None
    cli_version: str | None = None
    context_window: int | None = None
    invalid_lines: int = 0


"""Bounded repair loop with structural failure fingerprinting."""
from __future__ import annotations

from typing import Any

from .fingerprint import fingerprint
from .repair import REPAIRS


class StuckError(Exception):
    """Raised when the same structural failure fingerprint repeats >= 3 times."""


class ExhaustedError(Exception):
    """Raised when max_attempts completes without a passing tool result."""


class AgentLoop:
    """Executes tool calls with fingerprint-deduplicated structural repairs."""

    def __init__(
        self,
        tool: Any,
        generator: Any,
        repairs: list[Any] | None = None,
        max_attempts: int = 6,
    ):
        self.tool = tool
        self.generator = generator
        self.repairs = repairs if repairs is not None else REPAIRS
        self.max_attempts = max_attempts
        self.seen: dict[str, int] = {}

    def run(self, task: Any) -> Any:
        payload = self.generator(task)
        for _attempt in range(1, self.max_attempts + 1):
            result = self.tool(payload)
            if getattr(result, "ok", False):
                return result

            errors = getattr(result, "errors", None) or []
            fp = fingerprint(errors)
            count = self.seen.get(fp, 0) + 1
            self.seen[fp] = count

            if count >= 3:
                raise StuckError(f"identical failure {count}x: {fp}")

            payload = self._repair(payload, errors)
        raise ExhaustedError(f"{self.max_attempts} attempts, no pass")

    def _repair(self, payload: Any, errors: list[dict[str, Any]]) -> Any:
        mutated = False
        for err in errors:
            for match, fix in self.repairs:
                if match(err):
                    payload = fix(payload, err)
                    mutated = True
                    break
        if not mutated and hasattr(self.generator, "repair"):
            payload = self.generator.repair(payload, errors)
        return payload

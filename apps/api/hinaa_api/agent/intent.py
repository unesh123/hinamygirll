from __future__ import annotations

import re
from typing import Any
from .contracts import IntentResult, TurnContext


class IntentInterpreter:
    def interpret(self, text: str | dict[str, Any], context: TurnContext | dict[str, Any] | None = None) -> IntentResult:
        import json
        
        # Handle dictionary input directly
        if isinstance(text, dict):
            try:
                goal = str(text.get("goal") or text.get("text") or "Conversation")
                intent = str(text.get("primary_intent") or "conversation")
                valid_intents = {"conversation", "information", "generation", "tool_action", "multi_step_task", "project_task", "cancellation", "retry", "status_request"}
                if intent not in valid_intents:
                    intent = "conversation"
                return IntentResult(
                    primary_intent=intent,
                    goal=goal,
                    requested_outcome=str(text.get("requested_outcome") or goal),
                    constraints=list(text.get("constraints") or []),
                    required_modalities=list(text.get("required_modalities") or []),
                    candidate_tools=list(text.get("candidate_tools") or []),
                    requires_planning=bool(text.get("requires_planning", intent in {"generation", "multi_step_task", "project_task", "tool_action"})),
                    requires_confirmation=bool(text.get("requires_confirmation", False)),
                    expected_response_type=str(text.get("expected_response_type") or "conversation"),
                    confidence=float(text.get("confidence", 0.85) if isinstance(text.get("confidence"), (int, float)) else 0.85),
                )
            except Exception:
                return IntentResult(primary_intent="conversation", goal="fallback", confidence=0.5)

        # String input
        value = str(text).strip()
        
        # Try JSON parse if structured
        if value.startswith("{") or value.startswith("["):
            try:
                data = json.loads(value)
                if isinstance(data, dict):
                    return self.interpret(data, context)
            except Exception:
                # Deterministic fallback on malformed structured output
                return IntentResult(primary_intent="conversation", goal=value[:200], requested_outcome=value[:200], confidence=0.5)

        lower = value.lower()
        if re.search(r"\b(cancel|stop|abort)\b", lower):
            intent = "cancellation"
        elif re.search(r"\b(retry|try again)\b", lower):
            intent = "retry"
        elif re.search(r"\b(status|progress|how is it going|inspect run)\b", lower):
            intent = "status_request"
        elif re.search(r"\b(generate|create|make|build)\b", lower) and re.search(r"\b(pdf|image|document|code)\b", lower):
            intent = "generation"
        elif re.search(r"\b(search|research|latest|current|who is|what is)\b", lower):
            intent = "information"
        elif re.search(r"\b(and then|step by step|compare .* and)\b", lower):
            intent = "multi_step_task"
        else:
            intent = "conversation"
        return IntentResult(primary_intent=intent, goal=value, requested_outcome=value, requires_planning=intent in {"generation", "multi_step_task", "project_task", "tool_action"}, confidence=0.75)



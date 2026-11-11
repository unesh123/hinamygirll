"""A decision recommendation never grants permission to execute its outcome."""
from ..config import get_settings
from ..providers.bivia import BiviaDecisionRequest, decide
from .registry import ToolDefinition, registry


async def bivia_decide_handler(params: BiviaDecisionRequest) -> dict:
    return await decide(get_settings(), params)


registry.register(ToolDefinition(
    name="bivia_decide", display_name="Bivia decision",
    description="Choose among explicit outcomes from supplied context. Returns a recommendation or abstention, never execution authorization. Not a chat or content-generation model.",
    parameters={
        "state": {"type": "string", "description": "Relevant context for this decision"},
        "question": {"type": "string", "description": "The decision question"},
        "outcomes": {"type": "array", "items": {"type": "string"}, "description": "2–20 distinct candidate outcomes"},
        "mode": {"type": "string", "enum": ["fast", "deep"]},
        "allow_abstain": {"type": "boolean", "default": True},
    }, required_parameters=["state", "question", "outcomes"],
    risk_level="low", is_read_only=True, max_retries=0,
), bivia_decide_handler)

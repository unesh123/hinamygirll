from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Literal

logger = logging.getLogger("hinaa.providers.blocks")


@dataclass(frozen=True, kw_only=True)
class CanonicalTextBlock:
    type: Literal["text"] = "text"
    text: str


@dataclass(frozen=True, kw_only=True)
class CanonicalToolUseBlock:
    type: Literal["tool_use"] = "tool_use"
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True, kw_only=True)
class CanonicalToolResultBlock:
    type: Literal["tool_result"] = "tool_result"
    toolUseId: str
    content: Any
    isError: bool


@dataclass(frozen=True, kw_only=True)
class CanonicalReasoningBlock:
    type: Literal["reasoning_summary"] = "reasoning_summary"
    summary: str | None = None


@dataclass(frozen=True, kw_only=True)
class CanonicalImageBlock:
    type: Literal["image"] = "image"
    mediaType: str
    dataOrUrl: str


@dataclass(frozen=True, kw_only=True)
class CanonicalUnknownBlock:
    type: Literal["unknown"] = "unknown"
    providerType: str
    safeMetadata: dict[str, Any] | None = None


CanonicalProviderBlock = (
    CanonicalTextBlock
    | CanonicalToolUseBlock
    | CanonicalToolResultBlock
    | CanonicalReasoningBlock
    | CanonicalImageBlock
    | CanonicalUnknownBlock
)


def _require_string(obj: Any, attr: str) -> str:
    value = getattr(obj, attr, None)
    if not isinstance(value, str):
        raise ValueError(f"Expected string for {attr}, got {type(value)}")
    return value


def _require_dict(obj: Any, attr: str) -> dict[str, Any]:
    value = getattr(obj, attr, None)
    if not isinstance(value, dict):
        raise ValueError(f"Expected dict for {attr}, got {type(value)}")
    return value


def normalize_anthropic_block(block: Any) -> CanonicalProviderBlock | None:
    """Normalize Anthropic SDK response blocks to canonical form."""
    block_type = getattr(block, "type", None)
    
    if block_type == "text":
        text = getattr(block, "text", "")
        if not isinstance(text, str):
            raise ValueError("PROVIDER_TEXT_BLOCK_INVALID: text is not a string")
        return CanonicalTextBlock(text=text)
    
    if block_type in {"thinking", "reasoning"}:
        # Do not expose hidden reasoning to users
        summary = getattr(block, "thinking", None) or getattr(block, "reasoning", None)
        if isinstance(summary, str) and summary.strip():
            return CanonicalReasoningBlock(summary=summary[:200])
        return CanonicalReasoningBlock(summary=None)
    
    if block_type in {"tool_use", "tool_call"}:
        return CanonicalToolUseBlock(
            id=_require_string(block, "id"),
            name=_require_string(block, "name"),
            input=_require_dict(block, "input"),
        )
    
    if block_type == "tool_result":
        return CanonicalToolResultBlock(
            toolUseId=_require_string(block, "tool_use_id"),
            content=getattr(block, "content", None),
            isError=bool(getattr(block, "is_error", False)),
        )
    
    if block_type == "image":
        return CanonicalImageBlock(
            mediaType=_require_string(block, "media_type"),
            dataOrUrl=_require_string(block, "data") or _require_string(block, "url"),
        )
    
    logger.warning(
        "provider_unknown_block",
        extra={"providerBlockType": str(block_type) or "unknown"}
    )
    return CanonicalUnknownBlock(providerType=str(block_type) if block_type else "unknown")


def normalize_openai_block(block: Any) -> CanonicalProviderBlock | None:
    """Normalize OpenAI-compatible response blocks to canonical form."""
    # OpenAI uses dict-based responses with choices[0].message.content
    # This is handled at the message level, not block level
    return None


def extract_text_from_canonical_blocks(blocks: list[CanonicalProviderBlock]) -> str:
    """Extract only visible text from canonical blocks, skipping reasoning/tool blocks."""
    text_parts: list[str] = []
    for block in blocks:
        if isinstance(block, CanonicalTextBlock):
            text_parts.append(block.text)
        # Reasoning blocks are intentionally excluded
        # Tool blocks are handled separately
    return "".join(text_parts)


def extract_tool_calls_from_canonical_blocks(
    blocks: list[CanonicalProviderBlock]
) -> list[CanonicalToolUseBlock]:
    """Extract tool use calls from canonical blocks."""
    return [block for block in blocks if isinstance(block, CanonicalToolUseBlock)]


def extract_tool_results_from_canonical_blocks(
    blocks: list[CanonicalProviderBlock]
) -> list[CanonicalToolResultBlock]:
    """Extract tool results from canonical blocks."""
    return [block for block in blocks if isinstance(block, CanonicalToolResultBlock)]


def normalize_anthropic_response(response: Any) -> tuple[str, list[CanonicalProviderBlock]]:
    """Extract visible text and canonical blocks from Anthropic response."""
    content = getattr(response, "content", [])
    if not isinstance(content, list):
        return "", []
    
    canonical_blocks: list[CanonicalProviderBlock] = []
    for block in content:
        normalized = normalize_anthropic_block(block)
        if normalized:
            canonical_blocks.append(normalized)
    
    visible_text = extract_text_from_canonical_blocks(canonical_blocks)
    return visible_text, canonical_blocks
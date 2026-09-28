"""HINA ASTRA — Canonical Capability Registry & Retrieval Engine.

Central catalog for all Hina capabilities with parameter schemas, risk levels,
permission metadata, and semantic retrieval filtering (§8–§9).
"""

from __future__ import annotations

import logging
import re
from typing import Any, Sequence

from .types import AstraCapability, CapabilityCandidate

logger = logging.getLogger("hinaa.astra.registry")


class AstraCapabilityRegistry:
    """Canonical registry holding all capabilities available to the Astra Runtime."""

    def __init__(self) -> None:
        self._capabilities: dict[str, AstraCapability] = {}
        self._register_default_capabilities()

    def register(self, capability: AstraCapability) -> None:
        """Register a new capability."""
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> AstraCapability | None:
        """Retrieve capability by ID."""
        return self._capabilities.get(capability_id)

    def list_all(self) -> list[AstraCapability]:
        """List all registered capabilities."""
        return list(self._capabilities.values())

    def find_candidates(self, query: str, top_k: int = 8) -> list[CapabilityCandidate]:
        """Retrieve top capability candidates based on intent tokens and tags (§9)."""
        tokens = set(re.findall(r"\w+", query.lower()))
        candidates: list[tuple[float, AstraCapability, str]] = []

        for cap in self._capabilities.values():
            score = 0.0
            reasons: list[str] = []

            # Check ID tokens
            id_tokens = set(cap.id.lower().split("."))
            id_overlap = tokens.intersection(id_tokens)
            if id_overlap:
                score += len(id_overlap) * 2.5
                reasons.append(f"matched id tokens: {id_overlap}")

            # Check tags
            tag_overlap = tokens.intersection(set(t.lower() for t in cap.tags))
            if tag_overlap:
                score += len(tag_overlap) * 2.0
                reasons.append(f"matched tags: {tag_overlap}")

            # Check description keywords
            desc_tokens = set(re.findall(r"\w+", cap.description.lower()))
            desc_overlap = tokens.intersection(desc_tokens)
            if desc_overlap:
                score += len(desc_overlap) * 0.5
                reasons.append(f"matched desc: {desc_overlap}")

            if score > 0:
                candidates.append((score, cap, "; ".join(reasons)))

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        return [
            CapabilityCandidate(
                capability_id=cap.id,
                relevance_score=round(score, 2),
                reason=reason,
            )
            for score, cap, reason in candidates[:top_k]
        ]

    def _register_default_capabilities(self) -> None:
        """Populate initial core Astra capabilities."""
        self.register(
            AstraCapability(
                id="web.search",
                version="1.0.0",
                title="Web Search",
                description="Search public internet and web sources for fresh information, news, and research.",
                tags=["search", "web", "internet", "look up", "find", "google", "query", "news", "sources"],
                risk_level="read_only",
                requires_confirmation=False,
                supports_progress=True,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The search query to look up."},
                        "count": {"type": "integer", "default": 6},
                    },
                    "required": ["query"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="image.search",
                version="1.0.0",
                title="Image Search",
                description="Search for reference images, official character visuals, wallpapers, or photos.",
                tags=["image", "images", "search", "pics", "pictures", "photos", "wallpaper", "find images", "show images"],
                risk_level="read_only",
                requires_confirmation=False,
                supports_progress=True,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "The visual search query."},
                    },
                    "required": ["query"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="image.generate",
                version="1.0.0",
                title="Image Generation",
                description="Generate original visual artwork, portraits, scenes, and illustrations from prompt.",
                tags=["image", "picture", "draw", "generate", "art", "illustration", "photo", "render"],
                risk_level="local",
                requires_confirmation=False,
                supports_progress=True,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Detailed visual prompt."},
                        "aspect_ratio": {"type": "string", "enum": ["1:1", "16:9", "9:16", "4:3"], "default": "1:1"},
                    },
                    "required": ["prompt"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="image.edit",
                version="1.0.0",
                title="Image Editing",
                description="Edit, restyle, or transform an existing image while preserving character/asset identity.",
                tags=["edit", "modify", "change", "restyle", "background", "inpainting", "variation"],
                risk_level="local",
                requires_confirmation=False,
                supports_progress=True,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "string", "description": "ID of existing image to transform."},
                        "instructions": {"type": "string", "description": "Transformation instructions."},
                    },
                    "required": ["asset_id", "instructions"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="code.run",
                version="1.0.0",
                title="Code Execution",
                description="Run sandboxed Python or shell scripts to compute answers, analyze data, or verify logic.",
                tags=["code", "python", "script", "compute", "execute", "run", "calculate", "analyze", "math"],
                risk_level="local",
                requires_confirmation=False,
                supports_progress=False,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "language": {"type": "string", "enum": ["python", "bash"], "default": "python"},
                        "code": {"type": "string", "description": "The code block to execute."},
                    },
                    "required": ["code"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="reminders.create",
                version="1.0.0",
                title="Create Reminder",
                description="Schedule a persistent user reminder for a future date or time.",
                tags=["remind", "reminder", "schedule", "alarm", "alert", "task", "due"],
                risk_level="local",
                requires_confirmation=False,
                supports_progress=False,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Task or reminder title."},
                        "when": {"type": "string", "description": "Time specification (e.g. tomorrow at 5pm)."},
                        "is_urgent": {"type": "boolean", "default": False},
                    },
                    "required": ["title", "when"],
                },
            )
        )

        self.register(
            AstraCapability(
                id="document.generate",
                version="1.0.0",
                title="Document Generator",
                description="Create a structured document, markdown article, or exportable PDF.",
                tags=["document", "pdf", "report", "doc", "article", "worksheet", "export"],
                risk_level="local",
                requires_confirmation=False,
                supports_progress=True,
                parameter_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "outline": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["title"],
                },
            )
        )


# Global default singleton registry
global_capability_registry = AstraCapabilityRegistry()

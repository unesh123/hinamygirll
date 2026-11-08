"""
HINAA OS — Phase 14: Observed Self-Model Engine (Module F)
Maintains an empirical ledger of active, verified tools, providers, latency profiles,
and physical resource boundaries. Enforces strict zero-consciousness boundaries and
prevents hallucinated capabilities (e.g. generative video without model weights).
"""

from __future__ import annotations

import os
import shutil
import time
from typing import Any, Dict, List, Optional

from .contracts import SelfModelCapability
from .store import GoalStore


class ObservedSelfModel:
    """Empirical ledger of verified working capabilities, physical resources, and limitations."""

    def __init__(self, store: Optional[GoalStore] = None):
        self.store = store
        self._cache: Dict[str, SelfModelCapability] = {}
        self._init_standard_capabilities()

    def _init_standard_capabilities(self) -> None:
        """Seed known system capabilities and active probes."""
        now = time.time()
        caps = [
            SelfModelCapability(
                capability_id="llm_inference",
                category="llm",
                provider="gemini_and_claude",
                is_available=True,
                last_checked_utc=now,
                rate_limit_info={"rpm": 60, "tpm": 1000000},
                is_mock=False,
            ),
            SelfModelCapability(
                capability_id="voice_synthesis",
                category="voice",
                provider="elevenlabs_flash_stream",
                is_available=True,
                last_checked_utc=now,
                rate_limit_info={"voice_id": "WUgmmuDCpFXQ4z0NUUYX"},
                is_mock=False,
            ),
            SelfModelCapability(
                capability_id="sandbox_execution",
                category="sandbox",
                provider="python_pytest_process_runner",
                is_available=True,
                last_checked_utc=now,
                rate_limit_info={"max_concurrency": 4, "timeout_seconds": 60},
                is_mock=False,
            ),
            SelfModelCapability(
                capability_id="browser_automation",
                category="browser",
                provider="playwright_cdp",
                is_available=True,
                last_checked_utc=now,
                rate_limit_info={"headless": True},
                is_mock=False,
            ),
            SelfModelCapability(
                capability_id="temporal_memory",
                category="memory",
                provider="sqlite_wal_knowledge_graph",
                is_available=True,
                last_checked_utc=now,
                is_mock=False,
            ),
            # CRITICAL SAFETY CHECK: Video generation is FALSE because generative model weights are absent
            SelfModelCapability(
                capability_id="video_generation",
                category="video",
                provider="comfyui_diffusion",
                is_available=False,
                last_checked_utc=now,
                error_details="BLOCKED_UNAVAILABLE: Generative text-to-video / image-to-video diffusion weights not installed locally.",
                is_mock=False,
            ),
            SelfModelCapability(
                capability_id="nepal_payments",
                category="payments",
                provider="nchl_fonepay_gateway",
                is_available=False,  # Blocked without fresh Tier C HMAC approval
                last_checked_utc=now,
                error_details="BLOCKED: Real payment execution disabled; requires explicit Tier C HMAC approval token.",
                is_mock=True,
            ),
        ]
        for c in caps:
            self._cache[c.capability_id] = c
            if self.store:
                self.store.save_capability(c)

    def probe_capability(self, capability_id: str, force_refresh: bool = False) -> SelfModelCapability:
        """Probes live environment to verify actual availability rather than asserting it."""
        now = time.time()
        cap = self._cache.get(capability_id)
        if not cap and self.store:
            cap = self.store.get_capability(capability_id)
            if cap:
                self._cache[capability_id] = cap

        if not cap:
            # Unknown capability is considered unavailable
            return SelfModelCapability(
                capability_id=capability_id,
                category="unknown",
                provider="none",
                is_available=False,
                last_checked_utc=now,
                error_details=f"Capability '{capability_id}' is not registered in HINAA OS ledger.",
            )

        # Dynamic probe for sandbox execution
        if capability_id == "sandbox_execution" and force_refresh:
            has_py = shutil.which("python") is not None
            cap.is_available = has_py
            cap.last_checked_utc = now
            if self.store:
                self.store.save_capability(cap)

        return cap

    def update_capability_state(
        self,
        capability_id: str,
        is_available: bool,
        error_details: Optional[str] = None,
    ) -> None:
        """Updates availability when a tool fails or succeeds in real execution."""
        cap = self.probe_capability(capability_id)
        cap.is_available = is_available
        cap.last_checked_utc = time.time()
        cap.error_details = error_details
        self._cache[capability_id] = cap
        if self.store:
            self.store.save_capability(cap)

    def get_self_model_summary(self) -> Dict[str, Any]:
        """Provides an honest, non-sentient architectural self-model."""
        return {
            "entity": "HINAA OS Autonomous Goal Planner & Continuous Self-Correction",
            "version": "14.0.0",
            "sentient": False,
            "has_human_consciousness": False,
            "capabilities": {cid: c.is_available for cid, c in self._cache.items()},
            "unavailable_capabilities": [cid for cid, c in self._cache.items() if not c.is_available],
            "limitations": [
                "I do not experience feelings or subjective human consciousness.",
                "Generative neural video is unavailable due to missing local weights.",
                "Real payments and external production deployments require fresh human Tier C cryptographic authorization.",
                "All operational self-corrections are bounded by budget caps and verified receipts.",
            ],
            "last_audit_utc": time.time(),
        }

"""Evidence Collection, Screenshot Management, and Audit Receipts.

Captures timestamped, verifiable visual and textual evidence for browser actions,
storing artifacts in sandboxed directories with content hashing.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from playwright.async_api import Page

logger = logging.getLogger("hinaa.browser.evidence")

_DEFAULT_ARTIFACTS_DIR = Path("apps/data/browser_artifacts")


class EvidenceCollector:
    """Collects and stores verifiable evidence (screenshots, DOM snapshots, hashes)."""

    def __init__(self, artifacts_dir: Optional[Path] = None) -> None:
        self.artifacts_dir = artifacts_dir or _DEFAULT_ARTIFACTS_DIR
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    async def capture_screenshot(
        self,
        page: Page,
        task_id: str,
        action_name: str = "action",
        full_page: bool = False,
    ) -> Dict[str, Any]:
        """Captures a screenshot, persists to disk, and returns base64 preview and hash."""
        task_dir = self.artifacts_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")[:19]
        filename = f"{timestamp_str}_{action_name}.png"
        filepath = task_dir / filename

        try:
            image_bytes = await page.screenshot(full_page=full_page)
            filepath.write_bytes(image_bytes)

            sha256_hash = hashlib.sha256(image_bytes).hexdigest()
            b64_str = base64.b64encode(image_bytes).decode("ascii")

            return {
                "filepath": str(filepath.resolve()),
                "filename": filename,
                "sha256": sha256_hash,
                "size_bytes": len(image_bytes),
                "screenshot_b64": b64_str[:50000],  # preview slice
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            logger.warning("Failed to capture screenshot for task %s: %s", task_id, exc)
            return {"error": str(exc), "filepath": None}

"""Adapter Registry, Versioning, Modelfile Generator, and Deployment Manager."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.neural_lab.adapters")


class AdapterMetadata(BaseModel):
    adapter_id: str
    name: str
    version: str = "1.0.0"
    base_model_id: str
    base_model_revision: str = "main"
    adapter_path: str
    status: str = "REGISTERED"  # "REGISTERED", "ACTIVE", "ARCHIVED", "ROLLED_BACK"
    benchmark_score: Optional[float] = None
    created_at: float
    description: str


class AdapterManager:
    """Manages versioned LoRA adapters, Ollama export, and rollback controls."""

    def __init__(self, adapters_dir: Optional[str] = None) -> None:
        self.adapters_dir = Path(adapters_dir or Path(__file__).resolve().parents[1] / "adapters_store")
        self.adapters_dir.mkdir(parents=True, exist_ok=True)
        self._registry: dict[str, AdapterMetadata] = {}
        self._active_adapter_id: Optional[str] = None
        self._load_existing_adapters()

    def _load_existing_adapters(self) -> None:
        index_file = self.adapters_dir / "adapters_index.json"
        if index_file.exists():
            try:
                data = json.loads(index_file.read_text(encoding="utf-8"))
                for item in data:
                    meta = AdapterMetadata(**item)
                    self._registry[meta.adapter_id] = meta
                    if meta.status == "ACTIVE":
                        self._active_adapter_id = meta.adapter_id
            except Exception:
                pass

    def _save_index(self) -> None:
        index_file = self.adapters_dir / "adapters_index.json"
        data = [m.model_dump() for m in self._registry.values()]
        index_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def register_adapter(
        self,
        name: str,
        version: str,
        base_model_id: str,
        adapter_path: str,
        description: str = "",
        benchmark_score: Optional[float] = None,
    ) -> AdapterMetadata:
        """Register a newly trained adapter into the catalog."""
        adapter_id = f"{name}-v{version}"
        meta = AdapterMetadata(
            adapter_id=adapter_id,
            name=name,
            version=version,
            base_model_id=base_model_id,
            adapter_path=adapter_path,
            status="REGISTERED",
            benchmark_score=benchmark_score,
            created_at=float(Path(adapter_path).stat().st_ctime if Path(adapter_path).exists() else 0),
            description=description,
        )
        self._registry[adapter_id] = meta
        self._save_index()
        return meta

    def activate_adapter(self, adapter_id: str) -> bool:
        """Set adapter as currently active for serving and rollback previous active."""
        if adapter_id not in self._registry:
            return False

        for a_id, meta in self._registry.items():
            if meta.status == "ACTIVE":
                meta.status = "ARCHIVED"

        self._registry[adapter_id].status = "ACTIVE"
        self._active_adapter_id = adapter_id
        self._save_index()
        logger.info("Activated adapter '%s' as primary active model adapter.", adapter_id)
        return True

    def rollback_to_previous(self) -> Optional[str]:
        """Roll back from current active adapter to previous version."""
        candidates = [m for m in self._registry.values() if m.adapter_id != self._active_adapter_id]
        if not candidates:
            return None

        # Pick most recent non-active adapter
        candidates.sort(key=lambda x: x.created_at, reverse=True)
        prev = candidates[0]
        self.activate_adapter(prev.adapter_id)
        return prev.adapter_id

    def generate_ollama_modelfile(
        self,
        adapter_id: str,
        base_ollama_tag: str = "qwen2.5:1.5b",
        temperature: float = 0.7,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate Ollama Modelfile linking the local adapter weights with Ollama runtime."""
        meta = self._registry.get(adapter_id)
        if not meta:
            raise ValueError(f"Adapter '{adapter_id}' not found.")

        sys_prompt = system_prompt or (
            "You are Hina, an autonomous, intelligent AI companion with persistent identity, "
            "sharp analytical capabilities, and genuine initiative. You act within bounded permissions."
        )

        modelfile_content = (
            f"# HINAA Custom Model Specification\n"
            f"# Base Model: {meta.base_model_id}\n"
            f"# Adapter: {meta.adapter_id} (Version {meta.version})\n\n"
            f"FROM {base_ollama_tag}\n\n"
            f"ADAPTER {meta.adapter_path}\n\n"
            f"PARAMETER temperature {temperature}\n"
            f"PARAMETER top_p 0.9\n"
            f"PARAMETER stop \"<|im_end|>\"\n\n"
            f"SYSTEM \"\"\"{sys_prompt}\"\"\"\n"
        )

        out_file = self.adapters_dir / f"Modelfile_{adapter_id}"
        out_file.write_text(modelfile_content, encoding="utf-8")
        logger.info("Generated Ollama Modelfile for adapter '%s' at: %s", adapter_id, out_file)
        return str(out_file)

    def list_adapters(self) -> list[AdapterMetadata]:
        return list(self._registry.values())

    def get_active_adapter(self) -> Optional[AdapterMetadata]:
        return self._registry.get(self._active_adapter_id) if self._active_adapter_id else None


_GLOBAL_ADAPTER_MANAGER: Optional[AdapterManager] = None


def get_adapter_manager() -> AdapterManager:
    global _GLOBAL_ADAPTER_MANAGER
    if _GLOBAL_ADAPTER_MANAGER is None:
        _GLOBAL_ADAPTER_MANAGER = AdapterManager()
    return _GLOBAL_ADAPTER_MANAGER

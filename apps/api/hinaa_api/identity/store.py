"""Persistent storage engine for HINAA Character Identity profile."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from hinaa_api.identity.models import CharacterIdentity

logger = logging.getLogger("hinaa.identity.store")

DEFAULT_STORAGE_PATH = Path("data/identity/character_profile.json")


class IdentityStore:
    """Manages disk persistence and recovery of the CharacterIdentity model."""

    def __init__(self, file_path: Path | str | None = None) -> None:
        self.file_path = Path(file_path) if file_path else DEFAULT_STORAGE_PATH
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> CharacterIdentity:
        """Loads identity from file, or returns default if not found."""
        if not self.file_path.exists():
            logger.info("No saved identity profile found at %s. Creating default.", self.file_path)
            identity = CharacterIdentity()
            self.save(identity)
            return identity

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            identity = CharacterIdentity.model_validate(data)
            logger.info("Successfully loaded persistent identity '%s' (v%s)", identity.name, identity.version)
            return identity
        except Exception as exc:
            logger.error("Failed to parse identity profile at %s: %s. Using default.", self.file_path, exc)
            return CharacterIdentity()

    def save(self, identity: CharacterIdentity) -> bool:
        """Atomically saves the identity profile to disk."""
        try:
            temp_path = self.file_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(identity.model_dump(), f, indent=2)
            temp_path.replace(self.file_path)
            return True
        except Exception as exc:
            logger.error("Failed to save identity profile to %s: %s", self.file_path, exc)
            return False

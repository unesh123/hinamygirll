"""
HINAA OS — Conversational Spoken Topic Ledger (Module G)
Maintains working memory of discussed artifact topics, claims, narrative angles,
and user feedback across turns. Prevents unwanted repetition in follow-up queries,
respects tenant boundaries, and supports artifact deletion invalidation.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .contracts import SpokenTopicRecord

logger = logging.getLogger("hinaa.explanation.ledger")


class SpokenTopicLedger:
    """Persistent SQLite-backed and in-memory ledger tracking spoken topics."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        if db_path is None:
            # Default to standard data directory
            base_dir = Path(__file__).resolve().parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(base_dir / "spoken_topic_ledger.db")
        else:
            self._db_path = db_path

        self._memory_cache: Dict[str, List[SpokenTopicRecord]] = {}
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS spoken_topic_ledger (
                    record_id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    tenant_id TEXT NOT NULL,
                    claim_ids_explained TEXT NOT NULL,
                    narrative_angle TEXT,
                    examples_used TEXT,
                    last_speech_turn INTEGER NOT NULL,
                    user_feedback TEXT,
                    timestamp REAL NOT NULL
                );
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_conv_artifact
                ON spoken_topic_ledger(conversation_id, artifact_id);
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ledger_tenant
                ON spoken_topic_ledger(tenant_id);
            """)
            conn.commit()

    def record_turn(
        self,
        conversation_id: str,
        artifact_id: str,
        claim_ids: List[str],
        narrative_angle: str = "",
        examples_used: Optional[List[str]] = None,
        speech_turn: int = 1,
        user_feedback: Optional[str] = None,
        tenant_id: str = "default",
    ) -> SpokenTopicRecord:
        """Records an explanation turn in memory and SQLite."""
        record = SpokenTopicRecord(
            record_id=f"rec-{uuid.uuid4().hex[:8]}",
            conversation_id=conversation_id,
            artifact_id=artifact_id,
            tenant_id=tenant_id,
            claim_ids_explained=list(claim_ids),
            narrative_angle=narrative_angle,
            examples_used=list(examples_used or []),
            last_speech_turn=speech_turn,
            user_feedback=user_feedback,
            timestamp=time.time(),
        )

        # Update cache
        key = f"{tenant_id}:{conversation_id}:{artifact_id}"
        if key not in self._memory_cache:
            self._memory_cache[key] = []
        self._memory_cache[key].append(record)

        # Write to SQLite
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO spoken_topic_ledger (
                        record_id, conversation_id, artifact_id, tenant_id,
                        claim_ids_explained, narrative_angle, examples_used,
                        last_speech_turn, user_feedback, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.record_id,
                        record.conversation_id,
                        record.artifact_id,
                        record.tenant_id,
                        json.dumps(record.claim_ids_explained),
                        record.narrative_angle,
                        json.dumps(record.examples_used),
                        record.last_speech_turn,
                        record.user_feedback,
                        record.timestamp,
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning("Failed to persist spoken topic to SQLite: %s", e)

        return record

    def get_explained_claim_ids(
        self,
        conversation_id: str,
        artifact_id: str,
        tenant_id: str = "default",
    ) -> List[str]:
        """Returns all claim IDs already explained for this artifact in this conversation."""
        key = f"{tenant_id}:{conversation_id}:{artifact_id}"
        if key in self._memory_cache:
            claims: Set[str] = set()
            for rec in self._memory_cache[key]:
                claims.update(rec.claim_ids_explained)
            return list(claims)

        # Query SQLite
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT claim_ids_explained FROM spoken_topic_ledger
                    WHERE conversation_id = ? AND artifact_id = ? AND tenant_id = ?
                    """,
                    (conversation_id, artifact_id, tenant_id),
                )
                claims_set: Set[str] = set()
                for row in cur.fetchall():
                    raw = json.loads(row["claim_ids_explained"])
                    claims_set.update(raw)
                return list(claims_set)
        except Exception as e:
            logger.warning("Failed to query spoken claim IDs: %s", e)
            return []

    def get_prior_angles(
        self,
        conversation_id: str,
        artifact_id: str,
        tenant_id: str = "default",
    ) -> List[str]:
        """Returns narrative angles previously used to explain this artifact."""
        key = f"{tenant_id}:{conversation_id}:{artifact_id}"
        if key in self._memory_cache:
            return [rec.narrative_angle for rec in self._memory_cache[key] if rec.narrative_angle]

        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT narrative_angle FROM spoken_topic_ledger
                    WHERE conversation_id = ? AND artifact_id = ? AND tenant_id = ?
                    """,
                    (conversation_id, artifact_id, tenant_id),
                )
                return [row["narrative_angle"] for row in cur.fetchall() if row["narrative_angle"]]
        except Exception as e:
            logger.warning("Failed to query prior angles: %s", e)
            return []

    def invalidate_artifact(self, artifact_id: str, tenant_id: str = "default") -> int:
        """Prunes all records related to an invalidated or deleted artifact."""
        # Evict from cache
        keys_to_remove = [k for k in self._memory_cache if k.startswith(f"{tenant_id}:") and k.endswith(f":{artifact_id}")]
        for k in keys_to_remove:
            self._memory_cache.pop(k, None)

        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    DELETE FROM spoken_topic_ledger
                    WHERE artifact_id = ? AND tenant_id = ?
                    """,
                    (artifact_id, tenant_id),
                )
                conn.commit()
                return cur.rowcount
        except Exception as e:
            logger.warning("Failed to delete spoken topics for artifact %s: %s", artifact_id, e)
            return 0

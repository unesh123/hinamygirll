"""
HINAA OS — Phase 10 Transactional SQLite Memory Repository
Full ACID persistence with WAL mode, FTS5 full-text indexing,
schema migrations, audit logging, and deletion cascades.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from ..persistence import sqlcompat
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .privacy import MemoryPrivacyGuard
from .schemas import (
    CandidateStatus,
    IngestionCandidate,
    KnowledgeEdge,
    KnowledgeNode,
    MemoryEvent,
    MemoryRecord,
    MemoryScope,
    MemoryStats,
    MemoryType,
    TrustTier,
    _now_iso,
)

logger = logging.getLogger("hinaa.memory.repository")

def _get_default_db_path() -> Path:
    try:
        from ..config import DATA_DIR
        return DATA_DIR / "hinaa_memory.db"
    except Exception:
        # Fallback relative to repository root
        base = Path(__file__).resolve().parents[3]
        return base / "apps" / "api" / "data" / "hinaa_memory.db"


class MemoryRepository:
    """ACID SQLite repository with WAL mode, FTS5 indexing, and cascade support."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        is_default = db_path is None
        raw_path = _get_default_db_path() if is_default else db_path
        self._pg = sqlcompat.pg_target(raw_path, is_default=is_default)
        if self._pg:
            self.db_path = raw_path
        elif str(raw_path) == ":memory:":
            self.db_path = ":memory:"
        else:
            self.db_path = Path(raw_path).resolve()
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_db()

    def _get_connection(self) -> Any:
        if self._pg:
            return sqlcompat.connect_pg(self._pg)
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode for granular transaction control
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _init_db(self) -> None:
        """Run initialization and idempotent schema migrations."""
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
                """
            )

            # Check if migration v1 applied
            cur = conn.execute("SELECT version FROM schema_migrations WHERE version = 'v1_phase10_init'")
            if not cur.fetchone():
                self._apply_migration_v1(conn)
                conn.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES ('v1_phase10_init', ?)",
                    (_now_iso(),),
                )
                logger.info("Applied migration v1_phase10_init to %s", self.db_path)

    def _apply_migration_v1(self, conn: sqlite3.Connection) -> None:
        """Create primary tables, FTS5 virtual table, triggers, and indices."""
        # 1. memories table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT,
                project_id TEXT,
                scope TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                content TEXT NOT NULL,
                structured_data TEXT,
                trust_tier TEXT NOT NULL,
                confidence REAL NOT NULL,
                source_url TEXT,
                source_tool TEXT,
                source_turn_id TEXT,
                evidence_text TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                is_contradicted INTEGER NOT NULL DEFAULT 0,
                superseded_by_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                embedding TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tenant_scope ON memories(tenant_id, scope, is_active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tenant_user ON memories(tenant_id, user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_tenant_proj ON memories(tenant_id, project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at)")

        # 2. FTS5 virtual table for full-text search (SQLite) or GIN tsvector index (Postgres)
        if self._pg:
            try:
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_memories_content_tsv ON memories USING gin(to_tsvector('simple', content))"
                )
            except Exception as e:
                logger.debug("Could not create postgres gin index: %s", e)
        else:
            conn.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    id UNINDEXED,
                    tenant_id UNINDEXED,
                    content,
                    tokenize='unicode61'
                )
                """
            )

            # Triggers to keep FTS5 synchronized with memories table
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_insert AFTER INSERT ON memories
                BEGIN
                    INSERT INTO memory_fts(id, tenant_id, content)
                    VALUES (new.id, new.tenant_id, new.content);
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_delete AFTER DELETE ON memories
                BEGIN
                    DELETE FROM memory_fts WHERE id = old.id;
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_memories_update AFTER UPDATE OF content ON memories
                BEGIN
                    DELETE FROM memory_fts WHERE id = old.id;
                    INSERT INTO memory_fts(id, tenant_id, content)
                    VALUES (new.id, new.tenant_id, new.content);
                END;
                """
            )

        # 3. knowledge_nodes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_nodes (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                scope TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                canonical_name TEXT NOT NULL,
                aliases TEXT,
                attributes TEXT,
                created_at TEXT NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_knodes_tenant_name ON knowledge_nodes(tenant_id, canonical_name)")

        # 4. knowledge_edges table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_edges (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                target_id TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                evidence_id TEXT,
                confidence REAL NOT NULL,
                valid_from TEXT NOT NULL,
                valid_to TEXT,
                is_contradiction INTEGER NOT NULL DEFAULT 0,
                superseded_by TEXT,
                metadata TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kedges_tenant_src ON knowledge_edges(tenant_id, source_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kedges_tenant_tgt ON knowledge_edges(tenant_id, target_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_kedges_evidence ON knowledge_edges(evidence_id)")

        # 5. ingestion_candidates table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS ingestion_candidates (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                candidate_fact TEXT NOT NULL,
                source_url TEXT,
                source_tool TEXT,
                raw_evidence TEXT,
                extracted_entities TEXT,
                trust_tier TEXT NOT NULL,
                status TEXT NOT NULL,
                review_notes TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_ingest_status ON ingestion_candidates(tenant_id, status)")

        # 6. memory_events table (audit log)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memory_events (
                id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                target_id TEXT NOT NULL,
                target_type TEXT NOT NULL,
                details TEXT,
                timestamp TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mevents_tenant ON memory_events(tenant_id, timestamp)")

    # -----------------------------------------------------------------------
    # Memory CRUD Operations
    # -----------------------------------------------------------------------

    def save_memory(self, record: MemoryRecord) -> MemoryRecord:
        """Persist a memory record with sanitization and audit log."""
        # Sanitize content
        sanitized_content = MemoryPrivacyGuard.sanitize_content(record.content)
        record.content = sanitized_content

        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    """
                    INSERT INTO memories (
                        id, tenant_id, user_id, project_id, scope, memory_type,
                        content, structured_data, trust_tier, confidence,
                        source_url, source_tool, source_turn_id, evidence_text,
                        is_active, is_contradicted, superseded_by_id,
                        created_at, updated_at, expires_at, embedding
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.tenant_id,
                        record.user_id,
                        record.project_id,
                        record.scope.value if isinstance(record.scope, MemoryScope) else record.scope,
                        record.memory_type.value if isinstance(record.memory_type, MemoryType) else record.memory_type,
                        record.content,
                        json.dumps(record.structured_data, ensure_ascii=False),
                        record.trust_tier.value if isinstance(record.trust_tier, TrustTier) else record.trust_tier,
                        record.confidence,
                        record.source_url,
                        record.source_tool,
                        record.source_turn_id,
                        record.evidence_text,
                        1 if record.is_active else 0,
                        1 if record.is_contradicted else 0,
                        record.superseded_by_id,
                        record.created_at,
                        record.updated_at,
                        record.expires_at,
                        json.dumps(record.embedding) if record.embedding is not None else None,
                    ),
                )
                # Audit event
                conn.execute(
                    """
                    INSERT INTO memory_events (id, tenant_id, event_type, target_id, target_type, details, timestamp)
                    VALUES (?, ?, 'create', ?, 'memory', ?, ?)
                    """,
                    (
                        _now_iso() + "-" + record.id[:8],
                        record.tenant_id,
                        record.id,
                        json.dumps({"scope": str(record.scope), "trust_tier": str(record.trust_tier)}),
                        _now_iso(),
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return record

    def get_memory(self, memory_id: str, tenant_id: str = "default") -> Optional[MemoryRecord]:
        """Fetch memory record by id ensuring tenant isolation."""
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_memory(row)

    def update_memory(
        self,
        memory_id: str,
        updates: dict[str, Any],
        tenant_id: str = "default",
        reason: Optional[str] = None,
    ) -> Optional[MemoryRecord]:
        """Update memory fields and record audit trail."""
        existing = self.get_memory(memory_id, tenant_id)
        if not existing:
            return None

        # Build update query
        fields: list[str] = []
        params: list[Any] = []

        if "content" in updates and updates["content"] is not None:
            clean_content = MemoryPrivacyGuard.sanitize_content(updates["content"])
            fields.append("content = ?")
            params.append(clean_content)
        if "structured_data" in updates and updates["structured_data"] is not None:
            fields.append("structured_data = ?")
            params.append(json.dumps(updates["structured_data"], ensure_ascii=False))
        if "confidence" in updates and updates["confidence"] is not None:
            fields.append("confidence = ?")
            params.append(float(updates["confidence"]))
        if "is_active" in updates and updates["is_active"] is not None:
            fields.append("is_active = ?")
            params.append(1 if updates["is_active"] else 0)
        if "is_contradicted" in updates and updates["is_contradicted"] is not None:
            fields.append("is_contradicted = ?")
            params.append(1 if updates["is_contradicted"] else 0)
        if "superseded_by_id" in updates:
            fields.append("superseded_by_id = ?")
            params.append(updates["superseded_by_id"])
        if "expires_at" in updates:
            fields.append("expires_at = ?")
            params.append(updates["expires_at"])
        if "embedding" in updates:
            fields.append("embedding = ?")
            params.append(json.dumps(updates["embedding"]) if updates["embedding"] is not None else None)

        now_str = _now_iso()
        fields.append("updated_at = ?")
        params.append(now_str)

        params.extend([memory_id, tenant_id])

        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                conn.execute(
                    f"UPDATE memories SET {', '.join(fields)} WHERE id = ? AND tenant_id = ?",
                    params,
                )
                conn.execute(
                    """
                    INSERT INTO memory_events (id, tenant_id, event_type, target_id, target_type, details, timestamp)
                    VALUES (?, ?, 'update', ?, 'memory', ?, ?)
                    """,
                    (
                        _now_iso() + "-" + memory_id[:8],
                        tenant_id,
                        memory_id,
                        json.dumps({"updates": list(updates.keys()), "reason": reason}),
                        now_str,
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise

        return self.get_memory(memory_id, tenant_id)

    def delete_memory(self, memory_id: str, tenant_id: str = "default", cascade: bool = True) -> bool:
        """Hard-delete memory with automatic cascade to knowledge edges and FTS index."""
        existing = self.get_memory(memory_id, tenant_id)
        if not existing:
            return False

        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                if cascade:
                    # Invalidate knowledge edges referencing this memory as evidence
                    conn.execute(
                        "DELETE FROM knowledge_edges WHERE evidence_id = ? AND tenant_id = ?",
                        (memory_id, tenant_id),
                    )

                # Delete memory (trigger handles memory_fts deletion)
                conn.execute("DELETE FROM memories WHERE id = ? AND tenant_id = ?", (memory_id, tenant_id))

                # Audit deletion
                conn.execute(
                    """
                    INSERT INTO memory_events (id, tenant_id, event_type, target_id, target_type, details, timestamp)
                    VALUES (?, ?, 'delete', ?, 'memory', ?, ?)
                    """,
                    (
                        _now_iso() + "-" + memory_id[:8],
                        tenant_id,
                        memory_id,
                        json.dumps({"cascade": cascade, "deleted_content_snippet": existing.content[:60]}),
                        _now_iso(),
                    ),
                )
                conn.execute("COMMIT")
            except Exception:
                conn.execute("ROLLBACK")
                raise
        return True

    def query_memories(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: Optional[MemoryScope] = None,
        memory_type: Optional[MemoryType] = None,
        include_contradicted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        """Query memory records with scope and tenant filtering."""
        where_clauses = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]

        if not include_contradicted:
            where_clauses.append("is_active = 1")
            where_clauses.append("is_contradicted = 0")

        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if project_id:
            where_clauses.append("project_id = ?")
            params.append(project_id)
        if scope:
            where_clauses.append("scope = ?")
            params.append(scope.value if isinstance(scope, MemoryScope) else scope)
        if memory_type:
            where_clauses.append("memory_type = ?")
            params.append(memory_type.value if isinstance(memory_type, MemoryType) else memory_type)

        where_sql = " AND ".join(where_clauses)
        params.extend([limit, offset])

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                f"SELECT * FROM memories WHERE {where_sql} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                params,
            )
            return [self._row_to_memory(row) for row in cur.fetchall()]

    def fts_search(
        self,
        query: str,
        tenant_id: str = "default",
        limit: int = 20,
    ) -> list[tuple[str, float]]:
        """Perform full-text search using FTS5 and return list of (memory_id, score)."""
        clean_q = query.strip()
        if not clean_q:
            return []

        # Sanitize query for FTS5 syntax
        sanitized_terms = [re.sub(r'[^\w\u0900-\u097F]', '', term) for term in clean_q.split()]
        sanitized_terms = [t for t in sanitized_terms if t]
        if not sanitized_terms:
            return []
        fts_query = " OR ".join(f'"{t}"*' for t in sanitized_terms)

        results: list[tuple[str, float]] = []
        with self._lock, self._get_connection() as conn:
            if self._pg:
                # 1. Native Postgres Full Text Search using websearch_to_tsquery or plainto_tsquery
                try:
                    cur = conn.execute(
                        """
                        SELECT id, ts_rank_cd(to_tsvector('simple', content), plainto_tsquery('simple', ?)) AS rank
                        FROM memories
                        WHERE tenant_id = ?
                          AND to_tsvector('simple', content) @@ plainto_tsquery('simple', ?)
                        ORDER BY rank DESC, created_at DESC
                        LIMIT ?
                        """,
                        (clean_q, tenant_id, clean_q, limit),
                    )
                    rows = cur.fetchall()
                    if rows:
                        for row in rows:
                            score = float(row["rank"]) if row["rank"] is not None else 1.0
                            results.append((row["id"], score))
                        return results
                except Exception as pg_fts_err:
                    logger.debug("Postgres tsvector search fallback: %s", pg_fts_err)

                # 2. Multi-term ILIKE ranking fallback on Postgres
                like_clauses = " OR ".join(["content ILIKE ?" for _ in sanitized_terms])
                score_terms = " + ".join(["(CASE WHEN content ILIKE ? THEN 1.0 ELSE 0.0 END)" for _ in sanitized_terms])
                params: list[Any] = [f"%{t}%" for t in sanitized_terms]
                params.append(tenant_id)
                params.extend([f"%{t}%" for t in sanitized_terms])
                params.append(limit)

                sql = f"""
                    SELECT id, ({score_terms}) AS rank
                    FROM memories
                    WHERE tenant_id = ? AND ({like_clauses})
                    ORDER BY rank DESC, created_at DESC
                    LIMIT ?
                """
                try:
                    cur = conn.execute(sql, tuple(params))
                    for row in cur.fetchall():
                        score = float(row["rank"]) if row["rank"] is not None else 1.0
                        results.append((row["id"], score))
                    return results
                except Exception as e:
                    logger.warning("Postgres multi-term ILIKE fallback error: %s", e)
                    cur = conn.execute(
                        """
                        SELECT id FROM memories
                        WHERE tenant_id = ? AND content ILIKE ?
                        LIMIT ?
                        """,
                        (tenant_id, f"%{clean_q}%", limit),
                    )
                    for row in cur.fetchall():
                        results.append((row["id"], 1.0))
                    return results

            fts_query = " OR ".join(f'"{t}"*' for t in sanitized_terms)
            try:
                cur = conn.execute(
                    """
                    SELECT id, rank FROM memory_fts
                    WHERE tenant_id = ? AND memory_fts MATCH ?
                    ORDER BY rank ASC
                    LIMIT ?
                    """,
                    (tenant_id, fts_query, limit),
                )
                for row in cur.fetchall():
                    # rank is negative in BM25 (more negative = better match)
                    score = abs(float(row["rank"])) if row["rank"] is not None else 1.0
                    results.append((row["id"], score))
            except (sqlite3.OperationalError, Exception) as e:
                logger.warning("FTS search syntax error '%s': %s", fts_query, e)
                # Fallback to simple LIKE query
                cur = conn.execute(
                    """
                    SELECT id FROM memories
                    WHERE tenant_id = ? AND content LIKE ?
                    LIMIT ?
                    """,
                    (tenant_id, f"%{clean_q}%", limit),
                )
                for row in cur.fetchall():
                    results.append((row["id"], 1.0))
        return results

    def purge_expired(self, current_time: Optional[str] = None) -> int:
        """Purge or deactivate expired memories past their TTL."""
        if current_time is None:
            current_time = _now_iso()

        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                cur = conn.execute(
                    """
                    SELECT id, tenant_id FROM memories
                    WHERE expires_at IS NOT NULL AND expires_at <= ? AND is_active = 1
                    """,
                    (current_time,),
                )
                expired_rows = cur.fetchall()
                count = len(expired_rows)
                if count > 0:
                    for row in expired_rows:
                        conn.execute(
                            "UPDATE memories SET is_active = 0 WHERE id = ?",
                            (row["id"],),
                        )
                        conn.execute(
                            """
                            INSERT INTO memory_events (id, tenant_id, event_type, target_id, target_type, details, timestamp)
                            VALUES (?, ?, 'purge', ?, 'memory', ?, ?)
                            """,
                            (
                                _now_iso() + "-" + row["id"][:8],
                                row["tenant_id"],
                                row["id"],
                                json.dumps({"reason": "expired_ttl", "cutoff": current_time}),
                                _now_iso(),
                            ),
                        )
                conn.execute("COMMIT")
                return count
            except Exception:
                conn.execute("ROLLBACK")
                raise

    # -----------------------------------------------------------------------
    # Knowledge Graph Operations
    # -----------------------------------------------------------------------

    def save_node(self, node: KnowledgeNode) -> KnowledgeNode:
        """Create or update a knowledge graph entity node."""
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_nodes (
                    id, tenant_id, scope, entity_type, canonical_name,
                    aliases, attributes, created_at, valid_from, valid_to
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    node.id,
                    node.tenant_id,
                    node.scope.value if isinstance(node.scope, MemoryScope) else node.scope,
                    node.entity_type,
                    node.canonical_name,
                    json.dumps(node.aliases, ensure_ascii=False),
                    json.dumps(node.attributes, ensure_ascii=False),
                    node.created_at,
                    node.valid_from,
                    node.valid_to,
                ),
            )
        return node

    def get_node(self, node_id: str, tenant_id: str = "default") -> Optional[KnowledgeNode]:
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM knowledge_nodes WHERE id = ? AND tenant_id = ?", (node_id, tenant_id))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_node(row)

    def find_node_by_name(self, name_or_alias: str, tenant_id: str = "default") -> Optional[KnowledgeNode]:
        """Find node matching canonical name or alias (case-insensitive)."""
        target = name_or_alias.strip().lower()
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE tenant_id = ? AND LOWER(canonical_name) = ?",
                (tenant_id, target),
            )
            row = cur.fetchone()
            if row:
                return self._row_to_node(row)

            # Search in aliases JSON
            cur = conn.execute(
                "SELECT * FROM knowledge_nodes WHERE tenant_id = ? AND aliases LIKE ?",
                (tenant_id, f'%"{target}"%'),
            )
            for r in cur.fetchall():
                node = self._row_to_node(r)
                if any(a.lower() == target for a in node.aliases):
                    return node
        return None

    def query_nodes(
        self,
        tenant_id: str = "default",
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[KnowledgeNode]:
        where_clauses = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]
        if entity_type:
            where_clauses.append("entity_type = ?")
            params.append(entity_type)
        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                f"SELECT * FROM knowledge_nodes WHERE {where_sql} LIMIT ?",
                params,
            )
            return [self._row_to_node(row) for row in cur.fetchall()]

    def delete_node(self, node_id: str, tenant_id: str = "default") -> bool:
        with self._lock, self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Delete connected edges
                conn.execute(
                    "DELETE FROM knowledge_edges WHERE (source_id = ? OR target_id = ?) AND tenant_id = ?",
                    (node_id, node_id, tenant_id),
                )
                conn.execute("DELETE FROM knowledge_nodes WHERE id = ? AND tenant_id = ?", (node_id, tenant_id))
                conn.execute("COMMIT")
                return True
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def save_edge(self, edge: KnowledgeEdge) -> KnowledgeEdge:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO knowledge_edges (
                    id, tenant_id, source_id, target_id, relation_type,
                    evidence_id, confidence, valid_from, valid_to,
                    is_contradiction, superseded_by, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    edge.id,
                    edge.tenant_id,
                    edge.source_id,
                    edge.target_id,
                    edge.relation_type,
                    edge.evidence_id,
                    edge.confidence,
                    edge.valid_from,
                    edge.valid_to,
                    1 if edge.is_contradiction else 0,
                    edge.superseded_by,
                    json.dumps(edge.metadata, ensure_ascii=False),
                ),
            )
        return edge

    def query_edges(
        self,
        tenant_id: str = "default",
        source_id: Optional[str] = None,
        target_id: Optional[str] = None,
        relation_type: Optional[str] = None,
        as_of_date: Optional[str] = None,
        limit: int = 100,
    ) -> list[KnowledgeEdge]:
        where_clauses = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]

        if source_id:
            where_clauses.append("source_id = ?")
            params.append(source_id)
        if target_id:
            where_clauses.append("target_id = ?")
            params.append(target_id)
        if relation_type:
            where_clauses.append("relation_type = ?")
            params.append(relation_type)
        if as_of_date:
            where_clauses.append("valid_from <= ? AND (valid_to IS NULL OR valid_to >= ?)")
            params.extend([as_of_date, as_of_date])

        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(f"SELECT * FROM knowledge_edges WHERE {where_sql} LIMIT ?", params)
            return [self._row_to_edge(row) for row in cur.fetchall()]

    def delete_edge(self, edge_id: str, tenant_id: str = "default") -> bool:
        with self._lock, self._get_connection() as conn:
            cur = conn.execute("DELETE FROM knowledge_edges WHERE id = ? AND tenant_id = ?", (edge_id, tenant_id))
            return cur.rowcount > 0

    # -----------------------------------------------------------------------
    # Ingestion Candidates Operations
    # -----------------------------------------------------------------------

    def save_candidate(self, candidate: IngestionCandidate) -> IngestionCandidate:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO ingestion_candidates (
                    id, tenant_id, candidate_fact, source_url, source_tool,
                    raw_evidence, extracted_entities, trust_tier, status,
                    review_notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.id,
                    candidate.tenant_id,
                    candidate.candidate_fact,
                    candidate.source_url,
                    candidate.source_tool,
                    candidate.raw_evidence,
                    json.dumps(candidate.extracted_entities, ensure_ascii=False),
                    candidate.trust_tier.value if isinstance(candidate.trust_tier, TrustTier) else candidate.trust_tier,
                    candidate.status.value if isinstance(candidate.status, CandidateStatus) else candidate.status,
                    candidate.review_notes,
                    candidate.created_at,
                ),
            )
        return candidate

    def get_candidate(self, candidate_id: str, tenant_id: str = "default") -> Optional[IngestionCandidate]:
        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM ingestion_candidates WHERE id = ? AND tenant_id = ?",
                (candidate_id, tenant_id),
            )
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_candidate(row)

    def update_candidate_status(
        self,
        candidate_id: str,
        status: CandidateStatus,
        review_notes: Optional[str] = None,
        tenant_id: str = "default",
    ) -> Optional[IngestionCandidate]:
        with self._lock, self._get_connection() as conn:
            conn.execute(
                """
                UPDATE ingestion_candidates
                SET status = ?, review_notes = ?
                WHERE id = ? AND tenant_id = ?
                """,
                (
                    status.value if isinstance(status, CandidateStatus) else status,
                    review_notes,
                    candidate_id,
                    tenant_id,
                ),
            )
        return self.get_candidate(candidate_id, tenant_id)

    def list_candidates(
        self,
        tenant_id: str = "default",
        status: Optional[CandidateStatus] = None,
        limit: int = 50,
    ) -> list[IngestionCandidate]:
        where_clauses = ["tenant_id = ?"]
        params: list[Any] = [tenant_id]
        if status:
            where_clauses.append("status = ?")
            params.append(status.value if isinstance(status, CandidateStatus) else status)
        where_sql = " AND ".join(where_clauses)
        params.append(limit)

        with self._lock, self._get_connection() as conn:
            cur = conn.execute(
                f"SELECT * FROM ingestion_candidates WHERE {where_sql} ORDER BY created_at DESC LIMIT ?",
                params,
            )
            return [self._row_to_candidate(row) for row in cur.fetchall()]

    # -----------------------------------------------------------------------
    # System Stats & Audit Log
    # -----------------------------------------------------------------------

    def get_stats(self, tenant_id: str = "default") -> MemoryStats:
        """Compute live counts, active records, and file size."""
        with self._lock, self._get_connection() as conn:
            total_m = conn.execute("SELECT COUNT(*) FROM memories WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
            active_m = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE tenant_id = ? AND is_active = 1 AND is_contradicted = 0",
                (tenant_id,),
            ).fetchone()[0]
            contradicted_m = conn.execute(
                "SELECT COUNT(*) FROM memories WHERE tenant_id = ? AND is_contradicted = 1",
                (tenant_id,),
            ).fetchone()[0]
            total_nodes = conn.execute("SELECT COUNT(*) FROM knowledge_nodes WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
            total_edges = conn.execute("SELECT COUNT(*) FROM knowledge_edges WHERE tenant_id = ?", (tenant_id,)).fetchone()[0]
            pending_cand = conn.execute(
                "SELECT COUNT(*) FROM ingestion_candidates WHERE tenant_id = ? AND status = 'pending'",
                (tenant_id,),
            ).fetchone()[0]

        db_size = self.db_path.stat().st_size if self.db_path.exists() else 0

        return MemoryStats(
            total_memories=total_m,
            active_memories=active_m,
            contradicted_memories=contradicted_m,
            total_nodes=total_nodes,
            total_edges=total_edges,
            pending_candidates=pending_cand,
            db_size_bytes=db_size,
            db_path=str(self.db_path),
        )

    # -----------------------------------------------------------------------
    # Internal Row Deserializers
    # -----------------------------------------------------------------------

    @staticmethod
    def _row_to_memory(row: sqlite3.Row) -> MemoryRecord:
        structured_data = json.loads(row["structured_data"]) if row["structured_data"] else {}
        embedding = json.loads(row["embedding"]) if row["embedding"] else None
        return MemoryRecord(
            id=row["id"],
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            project_id=row["project_id"],
            scope=MemoryScope(row["scope"]),
            memory_type=MemoryType(row["memory_type"]),
            content=row["content"],
            structured_data=structured_data,
            trust_tier=TrustTier(row["trust_tier"]),
            confidence=float(row["confidence"]),
            source_url=row["source_url"],
            source_tool=row["source_tool"],
            source_turn_id=row["source_turn_id"],
            evidence_text=row["evidence_text"],
            is_active=bool(row["is_active"]),
            is_contradicted=bool(row["is_contradicted"]),
            superseded_by_id=row["superseded_by_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
            embedding=embedding,
        )

    @staticmethod
    def _row_to_node(row: sqlite3.Row) -> KnowledgeNode:
        aliases = json.loads(row["aliases"]) if row["aliases"] else []
        attributes = json.loads(row["attributes"]) if row["attributes"] else {}
        return KnowledgeNode(
            id=row["id"],
            tenant_id=row["tenant_id"],
            scope=MemoryScope(row["scope"]),
            entity_type=row["entity_type"],
            canonical_name=row["canonical_name"],
            aliases=aliases,
            attributes=attributes,
            created_at=row["created_at"],
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
        )

    @staticmethod
    def _row_to_edge(row: sqlite3.Row) -> KnowledgeEdge:
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}
        return KnowledgeEdge(
            id=row["id"],
            tenant_id=row["tenant_id"],
            source_id=row["source_id"],
            target_id=row["target_id"],
            relation_type=row["relation_type"],
            evidence_id=row["evidence_id"],
            confidence=float(row["confidence"]),
            valid_from=row["valid_from"],
            valid_to=row["valid_to"],
            is_contradiction=bool(row["is_contradiction"]),
            superseded_by=row["superseded_by"],
            metadata=metadata,
        )

    @staticmethod
    def _row_to_candidate(row: sqlite3.Row) -> IngestionCandidate:
        entities = json.loads(row["extracted_entities"]) if row["extracted_entities"] else []
        return IngestionCandidate(
            id=row["id"],
            tenant_id=row["tenant_id"],
            candidate_fact=row["candidate_fact"],
            source_url=row["source_url"],
            source_tool=row["source_tool"],
            raw_evidence=row["raw_evidence"] or "",
            extracted_entities=entities,
            trust_tier=TrustTier(row["trust_tier"]),
            status=CandidateStatus(row["status"]),
            review_notes=row["review_notes"],
            created_at=row["created_at"],
        )

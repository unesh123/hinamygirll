"""Compounding Memory — SQLite FTS5 lesson store with recency decay & usage reinforcement."""

from __future__ import annotations

import math
import os
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from ..runtime_paths import project_root
from ..society.metrics import SocietyMetricsStore, get_society_metrics


def _default_lessons_db() -> Path:
    override = os.environ.get("HINAA_LESSONS_DB_PATH")
    if override:
        return Path(override)
    return project_root() / ".hina" / "lessons.db"


@dataclass(frozen=True)
class LessonRecord:
    id: int
    topic: str
    failure_pattern: str
    fix_pattern: str
    hits: int
    score: float
    created_at: float
    last_used_at: float


class LessonsStore:
    """Persistent repository of verified failure -> fix patterns."""

    def __init__(
        self,
        db_path: str | Path | None = None,
        *,
        metrics: SocietyMetricsStore | None = None,
    ) -> None:
        self.db_path = Path(db_path) if db_path else _default_lessons_db()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.metrics = metrics or get_society_metrics()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS lessons (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    failure_pattern TEXT NOT NULL,
                    fix_pattern TEXT NOT NULL,
                    hits INTEGER NOT NULL DEFAULT 1,
                    created_at REAL NOT NULL,
                    last_used_at REAL NOT NULL
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS lessons_fts USING fts5(
                    topic,
                    failure_pattern,
                    fix_pattern,
                    content='lessons',
                    content_rowid='id'
                );
                CREATE TRIGGER IF NOT EXISTS lessons_ai AFTER INSERT ON lessons BEGIN
                    INSERT INTO lessons_fts(rowid, topic, failure_pattern, fix_pattern)
                    VALUES (new.id, new.topic, new.failure_pattern, new.fix_pattern);
                END;
                CREATE TRIGGER IF NOT EXISTS lessons_ad AFTER DELETE ON lessons BEGIN
                    INSERT INTO lessons_fts(lessons_fts, rowid, topic, failure_pattern, fix_pattern)
                    VALUES ('delete', old.id, old.topic, old.failure_pattern, old.fix_pattern);
                END;
                """
            )

    def record_lesson(
        self,
        *,
        topic: str,
        failure_pattern: str,
        fix_pattern: str,
        now: float | None = None,
    ) -> int:
        ts = time.time() if now is None else now
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO lessons (topic, failure_pattern, fix_pattern, hits, created_at, last_used_at) "
                "VALUES (?, ?, ?, 1, ?, ?)",
                (topic.strip(), failure_pattern.strip(), fix_pattern.strip(), ts, ts),
            )
            lesson_id = int(cur.lastrowid)
        self.metrics.record_counter(
            "lessons_stored",
            1,
            event={"kind": "memory.lesson", "topic": topic.strip()[:80]},
        )
        return lesson_id

    def retrieve_lessons(
        self,
        query: str,
        *,
        k: int = 3,
        half_life_days: float = 30.0,
        now: float | None = None,
    ) -> list[LessonRecord]:
        clean = " ".join(w for w in query.strip().split() if w.isalnum() or "-" in w or "_" in w)
        ts = time.time() if now is None else now
        with self._connect() as conn:
            if clean:
                fts_q = " OR ".join(f'"{tok}"' for tok in clean.split()[:8])
                try:
                    rows = conn.execute(
                        """
                        SELECT l.*, bm25(lessons_fts) AS rank
                        FROM lessons_fts f
                        JOIN lessons l ON l.id = f.rowid
                        WHERE lessons_fts MATCH ?
                        LIMIT ?
                        """,
                        (fts_q, max(k * 4, 12)),
                    ).fetchall()
                except sqlite3.OperationalError:
                    rows = []
            else:
                rows = conn.execute("SELECT *, 0.0 AS rank FROM lessons ORDER BY last_used_at DESC LIMIT ?", (k * 4,)).fetchall()

            if not rows:
                rows = conn.execute(
                    "SELECT *, 0.0 AS rank FROM lessons ORDER BY last_used_at DESC LIMIT ?",
                    (max(k * 2, 8),),
                ).fetchall()

            scored: list[LessonRecord] = []
            for r in rows:
                age_days = max(0.0, (ts - float(r["last_used_at"])) / 86400.0)
                decay = math.exp(-age_days / max(1.0, half_life_days))
                freq_boost = 1.0 + math.log1p(int(r["hits"])) * 0.25
                bm25_score = max(0.2, 1.0 - float(r["rank"] or 0.0) * 0.1)
                total = round(decay * freq_boost * bm25_score, 4)
                scored.append(
                    LessonRecord(
                        id=int(r["id"]),
                        topic=str(r["topic"]),
                        failure_pattern=str(r["failure_pattern"]),
                        fix_pattern=str(r["fix_pattern"]),
                        hits=int(r["hits"]),
                        score=total,
                        created_at=float(r["created_at"]),
                        last_used_at=float(r["last_used_at"]),
                    )
                )

            scored.sort(key=lambda item: item.score, reverse=True)
            top = scored[:k]
            if top:
                for item in top:
                    conn.execute(
                        "UPDATE lessons SET hits = hits + 1, last_used_at = ? WHERE id = ?",
                        (ts, item.id),
                    )
                self.metrics.record_counter("lessons_applied", len(top))
            return top

    def prune_stale(self, *, max_age_days: float = 90.0, min_hits: int = 1, now: float | None = None) -> int:
        ts = time.time() if now is None else now
        cutoff = ts - (max_age_days * 86400.0)
        with self._connect() as conn:
            cur = conn.execute(
                "DELETE FROM lessons WHERE last_used_at < ? AND hits <= ?",
                (cutoff, min_hits),
            )
            return int(cur.rowcount)

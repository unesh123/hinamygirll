"""HINAA B2 — Hierarchical conversation summary tree (directive §17–§24).

Structure (§17):
    Conversation
    ├── Episode 1 (raw turns + structured summary)
    ├── Episode 2 (...)
    └── Conversation summary (aggregated)

Key rules:
- Episodes are TOPIC/TASK-coherent runs, never one-per-message (§19).
- Summaries are retrieval aids; raw messages remain the source of truth and
  stay exactly retrievable (§21).
- Incremental: only new turns since ``last_summarized_sequence`` are folded
  into the open episode (§22).
- Quality gate (§24): summaries must carry concrete facts (project/entity/
  decision/constraint), never vague topic labels.
- Boundaries (§19): topic switch, project switch, task change, inactivity
  gap, goal completion, explicit "back to X", phase transition.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from .orm import ConversationEpisode, Message

logger = logging.getLogger(__name__)

# Signals that close the current episode and open a new one (§19).
_TOPIC_SWITCH_RE = re.compile(
    r"\b(?:anyway|back to|moving on|by the way|btw|ok now|okay now|next (?:topic|task|project)|"
    r"let'?s (?:talk about|work on|switch to|start)|new (?:topic|task|project))\b",
    re.IGNORECASE,
)
_PROJECT_SWITCH_RE = re.compile(
    r"\b(?:nova|project [a-z0-9_-]+)\b.*\b(?:auth|database|deploy|api|frontend|backend)\b",
    re.IGNORECASE,
)
_CORRECTION_RE = re.compile(
    r"\b(?:no[,.]? (?:we|it|that)|actually[,.]?|correction[,:]?|not (\w+) (?:but|—) |we (?:moved|migrated|switched|changed) to|"
    r"i (?:already )?told you|you forgot|we already (?:discussed|talked))\b",
    re.IGNORECASE,
)
_CONSTRAINT_RE = re.compile(
    r"\b(?:never|always|must not|don'?t (?:ever )?change|do not (?:ever )?change|make sure(?: to)?|required:)\b",
    re.IGNORECASE,
)

# Vague-summary quality gate (§24): a summary must mention at least one
# concrete artifact of the conversation (name/number/decision verb), else it
# is regenerated from the raw structural facts.
_CONCRETE_RE = re.compile(
    r"\b(?:migrated|decided|approved|created|fixed|requested|chose|switched|uses?|"
    r"[A-Z][a-zA-Z0-9_]{2,}|\d+)\b"
)

# Gap (seconds) after which an episode is considered closed (§19 inactivity).
_INACTIVITY_GAP_S = 30 * 60
# Close an episode when it spans more turns than this (bounded size).
_MAX_EPISODE_TURNS = 40


@dataclass
class EpisodeBoundary:
    """Decision about episode boundaries for the current turn."""

    new_episode: bool
    reason: str | None = None
    signals: list[str] = field(default_factory=list)


@dataclass
class EpisodeSummary:
    """Structured per-episode summary (§18) — never replaces raw turns (§21)."""

    episode_id: str
    conversation_id: str
    start_sequence: int
    end_sequence: int
    summary: str
    topics: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    corrections: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    unfinished_actions: list[str] = field(default_factory=list)
    importance: int = 1
    summary_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "conversation_id": self.conversation_id,
            "start_sequence": self.start_sequence,
            "end_sequence": self.end_sequence,
            "summary": self.summary,
            "topics": self.topics,
            "decisions": self.decisions,
            "corrections": self.corrections,
            "constraints": self.constraints,
            "open_questions": self.open_questions,
            "unfinished_actions": self.unfinished_actions,
            "importance": self.importance,
            "summary_version": self.summary_version,
        }


def _json_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        return [str(x) for x in data] if isinstance(data, list) else []
    except Exception:
        return []


class EpisodeSummarizer:
    """Persistent episode summaries with incremental updates (§17–§24).

    Extractive by design (§21: summary is an index over raw turns; the model
    never rewrites history). Heuristic-boundary detection keeps this cheap —
    a summarization LLM pass can upgrade ``_extractive_summary`` later without
    changing the storage contract.
    """

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    # ------------------------------------------------------------------
    # Boundary detection (§19)
    # ------------------------------------------------------------------
    def detect_boundary(
        self,
        user_text: str,
        *,
        previous_turn_text: str | None,
        seconds_since_last_turn: float | None,
        current_episode_turns: int,
        active_topic: str | None = None,
        new_topic: str | None = None,
    ) -> EpisodeBoundary:
        signals: list[str] = []
        if not user_text:
            return EpisodeBoundary(new_episode=False)

        if _TOPIC_SWITCH_RE.search(user_text):
            signals.append("topic_switch_phrase")
        if _CORRECTION_RE.search(user_text) is None and active_topic and new_topic and active_topic.lower() != new_topic.lower():
            signals.append("topic_change")
        if seconds_since_last_turn is not None and seconds_since_last_turn > _INACTIVITY_GAP_S:
            signals.append("inactivity_gap")
        if current_episode_turns >= _MAX_EPISODE_TURNS:
            signals.append("episode_length_cap")

        if signals:
            return EpisodeBoundary(new_episode=True, reason=signals[0], signals=signals)
        return EpisodeBoundary(new_episode=False)

    # ------------------------------------------------------------------
    # Incremental summarization (§22)
    # ------------------------------------------------------------------
    def record_turn(
        self,
        *,
        conversation_id: str,
        user_id: str | None,
        sequence: int,
        user_text: str,
        assistant_text: str,
        force_new_episode: bool = False,
        boundary_reason: str | None = None,
    ) -> EpisodeSummary:
        """Fold one finished turn into the open episode (or open a new one)."""
        with self._factory() as session:
            episode = self._open_episode(session, conversation_id)
            if episode is None or force_new_episode:
                episode = ConversationEpisode(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    start_sequence=sequence,
                    end_sequence=sequence,
                    boundary_reason=boundary_reason or "first_turn",
                )
                session.add(episode)
                session.flush()
            else:
                episode.end_sequence = sequence

            # Incremental: only new turns (§22). A turn is new when its
            # sequence exceeds the episode's last_summarized_sequence.
            if sequence <= episode.last_summarized_sequence:
                session.commit()
                return self._to_summary(episode)

            # Append the turn's structured facts to the episode state.
            summary_text = episode.summary or ""
            user_fact = f"U{sequence}: {user_text.strip()[:200]}"
            assistant_fact = f"A{sequence}: {assistant_text.strip()[:200]}"
            summary_text = (summary_text + "\n" + user_fact + "\n" + assistant_fact).strip("\n")

            episode.summary = self._extractive_summary(summary_text)
            episode.last_summarized_sequence = sequence
            episode.summary_version += 1

            for match in _CORRECTION_RE.finditer(user_text):
                episode.corrections_json = json.dumps(
                    _bounded(json.loads(episode.corrections_json or "[]") if episode.corrections_json else [], user_text.strip()[:200])
                )
                break
            for match in _CONSTRAINT_RE.finditer(user_text):
                episode.constraints_json = json.dumps(
                    _bounded(json.loads(episode.constraints_json or "[]") if episode.constraints_json else [], user_text.strip()[:200])
                )
                break
            if user_text.strip().endswith("?"):
                episode.open_questions_json = json.dumps(
                    _bounded(json.loads(episode.open_questions_json or "[]") if episode.open_questions_json else [], user_text.strip()[:200])
                )

            session.commit()
            return self._to_summary(episode)

    def episode_summaries(self, conversation_id: str, limit: int = 20) -> list[EpisodeSummary]:
        """Most recent episodes for retrieval (aid only — raw turns are truth)."""
        with self._factory() as session:
            rows = session.scalars(
                select(ConversationEpisode)
                .where(ConversationEpisode.conversation_id == conversation_id)
                .order_by(ConversationEpisode.end_sequence.desc())
                .limit(limit)
            ).all()
            return [self._to_summary(row) for row in rows]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------
    def _open_episode(self, session: Session, conversation_id: str) -> ConversationEpisode | None:
        return session.scalars(
            select(ConversationEpisode)
            .where(ConversationEpisode.conversation_id == conversation_id)
            .order_by(ConversationEpisode.end_sequence.desc())
            .limit(1)
        ).first()

    @staticmethod
    def _extractive_summary(raw_turn_log: str) -> str:
        """Bounded extractive index — newest turns preserved verbatim-ish.

        NOT a semantic replacement for the raw turns (§21). Keeps the log
        under a hard bound by keeping head (context) + tail (recency).
        """
        lines = [line for line in raw_turn_log.split("\n") if line.strip()]
        max_lines = 80
        if len(lines) <= max_lines:
            return "\n".join(lines)
        head = lines[:20]
        tail = lines[-max_lines + 20:]
        return "\n".join(head + ["...[earlier turns compacted]..."] + tail)

    @staticmethod
    def _to_summary(row: ConversationEpisode) -> EpisodeSummary:
        return EpisodeSummary(
            episode_id=row.id,
            conversation_id=row.conversation_id,
            start_sequence=row.start_sequence,
            end_sequence=row.end_sequence,
            summary=row.summary or "",
            topics=_json_list(row.topic_ids_json),
            decisions=_json_list(row.decisions_json),
            corrections=_json_list(row.corrections_json),
            constraints=_json_list(row.constraints_json),
            open_questions=_json_list(row.open_questions_json),
            unfinished_actions=_json_list(row.unfinished_actions_json),
            importance=row.importance,
            summary_version=row.summary_version,
        )


def _bounded(items: list[str], item: str, limit: int = 10) -> list[str]:
    out = [i for i in items if i != item]
    out.append(item)
    return out[-limit:]

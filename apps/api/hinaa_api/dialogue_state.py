"""dialogue_state.py — P0 Continuous Conversational Mind

Provides the three pillars that eliminate Hina's state-loss bugs:

1. ``ConversationTurnState`` — in-process dataclass mirroring the DB row.
   Passed to every component that builds context or routes providers.

2. ``DialogueActResolver`` — classifies each user turn BEFORE model inference.
   Short messages like ``"hina"`` or ``"1147"`` get the right act (VOCATIVE /
   ANSWER) instead of being treated as new requests.

3. ``DialogueStateService`` — loads, updates, and persists state using the
   ``ConversationTurnState`` ORM row.  Tool failures call
   ``record_tool_failure()`` which only touches ``last_tool_state`` — never
   clears ``active_topic``, ``slots``, or pending items.

Pipeline order enforced by this module:
  CORRECTNESS → TASK COMPLETION → CONTEXT CONTINUITY → CLARITY → PERSONALITY
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger("hinaa.dialogue_state")

# ─────────────────────────────────────────────────────────────────────────────
# Dialogue Acts
# ─────────────────────────────────────────────────────────────────────────────

class DialogueAct(str, Enum):
    """Coarse dialogue act taxonomy sufficient for routing and slot resolution."""
    REQUEST     = "REQUEST"       # "search One Piece episode 1147"
    VOCATIVE    = "VOCATIVE"      # "hina", "hey", user calling Hina by name
    ANSWER      = "ANSWER"        # "1147", "yes", "season 2" — reply to pending Q
    CONFIRMATION = "CONFIRMATION"  # "yes" / "no" / "ok" — binary
    REACTION    = "REACTION"      # "wow", "lol", "omg" — social reaction, no task
    COMMAND     = "COMMAND"       # "/command" or imperative with verb
    CONTINUATION = "CONTINUATION" # "more", "continue", "and?" — extend last
    UNKNOWN     = "UNKNOWN"


# ─────────────────────────────────────────────────────────────────────────────
# Typed slot definitions
# ─────────────────────────────────────────────────────────────────────────────

class SlotType(str, Enum):
    """Semantic type for a slot value — prevents e.g. episode → chapter confusion."""
    ANIME_EPISODE   = "anime_episode"
    MANGA_CHAPTER   = "manga_chapter"
    SEASON          = "season"
    TIMESTAMP       = "timestamp"
    PERSON_NAME     = "person_name"
    MEDIA_TITLE     = "media_title"
    QUERY_STRING    = "query_string"
    NUMBER          = "number"
    BOOLEAN         = "boolean"
    FREE_TEXT       = "free_text"


class AssetSelectionSource(str, Enum):
    ORDINAL_REFERENCE = "ORDINAL_REFERENCE"
    UI_CLICK = "UI_CLICK"
    EXPLICIT_ASSET_REFERENCE = "EXPLICIT_ASSET_REFERENCE"
    TOOL_DEFAULT = "TOOL_DEFAULT"
    MEMORY_RECALL = "MEMORY_RECALL"


@dataclass
class Slot:
    value: Any
    slot_type: SlotType
    confidence: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {"value": self.value, "type": self.slot_type.value, "confidence": self.confidence}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Slot":
        return cls(
            value=d["value"],
            slot_type=SlotType(d.get("type", "free_text")),
            confidence=float(d.get("confidence", 1.0)),
        )


@dataclass
class ActiveGoal:
    """Explicit, persistent active goal tracking for the conversation."""
    goal: str
    acceptance_criteria: list[str] = field(default_factory=list)
    hard_constraints: list[str] = field(default_factory=list)
    known_facts: list[str] = field(default_factory=list)
    unknowns: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    status: str = "active"

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "acceptance_criteria": list(self.acceptance_criteria),
            "hard_constraints": list(self.hard_constraints),
            "known_facts": list(self.known_facts),
            "unknowns": list(self.unknowns),
            "dependencies": list(self.dependencies),
            "artifacts": list(self.artifacts),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ActiveGoal":
        return cls(
            goal=d.get("goal", ""),
            acceptance_criteria=list(d.get("acceptance_criteria") or []),
            hard_constraints=list(d.get("hard_constraints") or []),
            known_facts=list(d.get("known_facts") or []),
            unknowns=list(d.get("unknowns") or []),
            dependencies=list(d.get("dependencies") or []),
            artifacts=list(d.get("artifacts") or []),
            status=d.get("status", "active"),
        )


# ─────────────────────────────────────────────────────────────────────────────
# TurnSemanticFrame — current-turn semantic interpretation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TurnSemanticFrame:
    """Semantic framing of the current turn, combining dialogue act, entities,
    pronoun resolution status, depth, and research intent."""
    dialogue_act: DialogueAct
    explicit_subjects: tuple[str, ...] = ()
    referenced_subjects: tuple[str, ...] = ()
    locations: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    temporal_intent: str | None = None
    active_thread: str | None = None
    goal: str | None = None
    desired_action: str | None = None
    depth: str = "standard"  # quick, standard, detailed, deep, exhaustive
    research_need: str = "none"  # none, light, deep
    assets: tuple[dict[str, Any], ...] = ()
    referent_resolved: bool = True
    clarification_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "dialogue_act": self.dialogue_act.value if hasattr(self.dialogue_act, "value") else str(self.dialogue_act),
            "explicit_subjects": list(self.explicit_subjects),
            "referenced_subjects": list(self.referenced_subjects),
            "locations": list(self.locations),
            "events": list(self.events),
            "temporal_intent": self.temporal_intent,
            "active_thread": self.active_thread,
            "goal": self.goal,
            "desired_action": self.desired_action,
            "depth": self.depth,
            "research_need": self.research_need,
            "assets": list(self.assets),
            "referent_resolved": self.referent_resolved,
            "clarification_prompt": self.clarification_prompt,
        }


def build_semantic_turn_frame(
    text: str,
    state: "ConversationTurnState | None" = None,
    *,
    request: Any | None = None,
) -> TurnSemanticFrame:
    """Constructs a TurnSemanticFrame from text and durable state, verifying
    referent resolution before any research is triggered."""
    lowered = text.lower().strip()
    act = DialogueActResolver.resolve(text, state) if state else DialogueAct.REQUEST

    # 1. Detect explicit subjects, locations, and events
    explicit_subs: list[str] = []
    locations: list[str] = []
    events: list[str] = []
    temp_intent = None

    try:
        from hinaa_api.media.search_intelligence import (
            canonical_entity_from_text,
            _KNOWN_LOCATIONS_RE,
            _CURRENT_EVENT_MARKERS_RE,
            _TEMPORAL_ANCHOR_RE,
        )
        prof = canonical_entity_from_text(text)
        if prof:
            explicit_subs.append(prof.canonical_name)

        loc_m = _KNOWN_LOCATIONS_RE.search(lowered)
        if loc_m:
            locations.append(loc_m.group(0).title())

        evt_m = _CURRENT_EVENT_MARKERS_RE.search(lowered)
        if evt_m:
            events.append(evt_m.group(0).title())

        temp_m = _TEMPORAL_ANCHOR_RE.search(lowered)
        if temp_m:
            temp_intent = temp_m.group(0)
    except Exception:
        pass

    # 2. Check referent resolution for deictic/pronoun references
    referenced_subs: list[str] = []
    referent_resolved = True
    clarification_prompt = None

    pronoun_match = re.search(r"\b(her|him|she|he|them|they|it)\b", lowered)
    has_explicit_anchor = bool(explicit_subs or locations or events)

    if pronoun_match and not has_explicit_anchor:
        resolved_antecedent = None
        if state:
            if state.active_topic and not any(g in state.active_topic.lower() for g in ("general", "none", "chat")):
                resolved_antecedent = state.active_topic
            elif state.active_entities:
                resolved_antecedent = state.active_entities[0].get("name") or state.active_entities[0].get("canonical_name")
            elif getattr(state, "selected_asset", None):
                resolved_antecedent = state.selected_asset.get("title") or state.selected_asset.get("name")

        if resolved_antecedent:
            referenced_subs.append(resolved_antecedent)
            referent_resolved = True
        else:
            referent_resolved = False
            pronoun = pronoun_match.group(1).lower()
            if pronoun in ("her", "she"):
                clarification_prompt = "Who would you like to know more about? Could you specify who you're referring to?"
            elif pronoun in ("him", "he"):
                clarification_prompt = "Who would you like to know more about? Could you specify who you're referring to?"
            elif pronoun in ("them", "they"):
                clarification_prompt = "Could you clarify who or what you're referring to?"
            else:
                clarification_prompt = "Could you specify what subject you'd like more details on?"

    # 3. Depth & Research need
    depth = "standard"
    try:
        from hinaa_api.intelligence.answer_depth import AnswerDepthController
        d_enum = AnswerDepthController.infer_depth(text, active_goal=state.active_goal if state else None)
        depth = d_enum.value.lower()
    except Exception:
        pass

    research_need = "none"
    if referent_resolved:
        try:
            from hinaa_api.intelligence.research_detector import ResearchNeedDetector
            needs_res, _ = ResearchNeedDetector.needs_research(text)
            if needs_res:
                research_need = "light" if depth in ("quick", "standard") else "deep"
        except Exception:
            pass

    goal_str = state.active_goal.goal if (state and state.active_goal) else None

    return TurnSemanticFrame(
        dialogue_act=act,
        explicit_subjects=tuple(explicit_subs),
        referenced_subjects=tuple(referenced_subs),
        locations=tuple(locations),
        events=tuple(events),
        temporal_intent=temp_intent,
        active_thread=None,
        goal=goal_str,
        desired_action=None,
        depth=depth,
        research_need=research_need,
        referent_resolved=referent_resolved,
        clarification_prompt=clarification_prompt,
    )


# ─────────────────────────────────────────────────────────────────────────────
# ConversationTurnState — in-process object (mirrors DB row)
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ConversationTurnState:
    """Complete dialogue state for one conversation.

    Loaded at the start of each turn, updated during the turn, and persisted
    after the turn.  A tool failure updates ONLY ``last_tool_state`` —
    ``active_topic``, ``slots``, and ``pending_*`` are never cleared on error.
    """
    conversation_id: str
    user_id: str | None = None
    state_version: int = 1

    # Topic / intent
    active_topic: str | None = None
    active_intent: str | None = None

    # ── Active Goal & Hard Constraints (P0 Continuous Intelligence) ──────────
    active_goal: ActiveGoal | None = None

    # Typed slots: slot_name → Slot
    slots: dict[str, Slot] = field(default_factory=dict)

    # Pending stacks
    pending_question: dict[str, Any] | None = None      # {text, asked_at_turn}
    pending_confirmation: dict[str, Any] | None = None  # {text, action_id, asked_at_turn}
    pending_action: dict[str, Any] | None = None        # {action, params, created_at_turn}

    # Tool continuation
    last_tool_state: dict[str, Any] | None = None       # {tool, params, error, at_turn}

    # Active entities: list of {type, name, normalized}
    active_entities: list[dict[str, Any]] = field(default_factory=list)

    # Dialogue act classification
    last_dialogue_act: DialogueAct | None = None

    # Unresolved references
    unresolved_refs: list[str] = field(default_factory=list)

    # ── Action & Asset Ledger (P0 Real Runtime Repair) ────────────────────────
    last_assistant_action: dict[str, Any] | None = None
    last_generated_asset_ids: list[str] = field(default_factory=list)
    active_assets: list[dict[str, Any]] = field(default_factory=list)
    tool_result_sets: list[dict[str, Any]] = field(default_factory=list)
    selected_asset: dict[str, Any] | None = None

    turn_count: int = 0
    updated_at: datetime | None = None

    # ── Convenience helpers ────────────────────────────────────────────────────

    def has_active_context(self) -> bool:
        """True when there is enough dialogue context that fresh greetings are wrong."""
        return bool(
            self.active_topic
            or self.active_goal is not None
            or self.pending_question
            or self.pending_confirmation
            or self.pending_action
            or self.slots
            or self.last_assistant_action
            or self.last_generated_asset_ids
            or self.tool_result_sets
            or self.selected_asset
            or self.turn_count > 0
        )

    def should_use_fresh_greeting(self) -> bool:
        """Generic greeting is the last resort — only emit when nothing is active."""
        return not self.has_active_context()

    def get_slot(self, name: str) -> Slot | None:
        return self.slots.get(name)

    def set_slot(self, name: str, value: Any, slot_type: SlotType, confidence: float = 1.0) -> None:
        self.slots[name] = Slot(value=value, slot_type=slot_type, confidence=confidence)

    def clear_slot(self, name: str) -> None:
        self.slots.pop(name, None)

    def get_query_for_active_topic(self) -> str | None:
        """Build a fallback search query from active context when model omits one."""
        if not self.active_topic:
            return None
        parts = [self.active_topic]
        ep = self.get_slot("episode_number")
        if ep:
            parts.append(f"episode {ep.value}")
        ch = self.get_slot("chapter_number")
        if ch:
            parts.append(f"chapter {ch.value}")
        season = self.get_slot("season")
        if season:
            parts.append(f"season {season.value}")
        if self.active_intent and self.active_intent not in {"web_search", ""}:
            parts.append(self.active_intent)
        return " ".join(parts)

    # ── Serialisation helpers ─────────────────────────────────────────────────

    def to_orm_kwargs(self) -> dict[str, Any]:
        """Return dict suitable for ORM upsert."""
        return {
            "conversation_id": self.conversation_id,
            "user_id": self.user_id,
            "state_version": self.state_version,
            "active_topic": self.active_topic,
            "active_intent": self.active_intent,
            "active_goal_json": json.dumps(self.active_goal.to_dict()) if self.active_goal else None,
            "slots_json": json.dumps({k: v.to_dict() for k, v in self.slots.items()}),
            "pending_question_json": json.dumps(self.pending_question) if self.pending_question else None,
            "pending_confirmation_json": json.dumps(self.pending_confirmation) if self.pending_confirmation else None,
            "pending_action_json": json.dumps(self.pending_action) if self.pending_action else None,
            "last_tool_state_json": json.dumps(self.last_tool_state) if self.last_tool_state else None,
            "active_entities_json": json.dumps(self.active_entities),
            "last_dialogue_act": self.last_dialogue_act.value if self.last_dialogue_act else None,
            "unresolved_refs_json": json.dumps(self.unresolved_refs),
            "last_assistant_action_json": json.dumps(self.last_assistant_action) if self.last_assistant_action else None,
            "last_generated_asset_ids_json": json.dumps(self.last_generated_asset_ids),
            "active_assets_json": json.dumps(self.active_assets),
            "tool_result_sets_json": json.dumps(self.tool_result_sets),
            "selected_asset_json": json.dumps(self.selected_asset) if self.selected_asset else None,
            "turn_count": self.turn_count,
        }

    @classmethod
    def from_orm_row(cls, row: Any) -> "ConversationTurnState":
        """Reconstruct from an ORM ``ConversationTurnState`` row."""
        def _json(s: str | None, default: Any) -> Any:
            if not s:
                return default
            try:
                return json.loads(s)
            except Exception:
                return default

        raw_slots = _json(row.slots_json, {})
        slots = {k: Slot.from_dict(v) for k, v in raw_slots.items() if isinstance(v, dict)}

        raw_act = row.last_dialogue_act
        dialogue_act = None
        if raw_act:
            try:
                dialogue_act = DialogueAct(raw_act)
            except ValueError:
                pass

        raw_goal = _json(getattr(row, "active_goal_json", None), None)
        active_goal = ActiveGoal.from_dict(raw_goal) if isinstance(raw_goal, dict) else None

        return cls(
            conversation_id=row.conversation_id,
            user_id=row.user_id,
            state_version=row.state_version,
            active_topic=row.active_topic,
            active_intent=row.active_intent,
            active_goal=active_goal,
            slots=slots,
            pending_question=_json(row.pending_question_json, None),
            pending_confirmation=_json(row.pending_confirmation_json, None),
            pending_action=_json(row.pending_action_json, None),
            last_tool_state=_json(row.last_tool_state_json, None),
            active_entities=_json(row.active_entities_json, []),
            last_dialogue_act=dialogue_act,
            unresolved_refs=_json(row.unresolved_refs_json, []),
            last_assistant_action=_json(getattr(row, "last_assistant_action_json", None), None),
            last_generated_asset_ids=_json(getattr(row, "last_generated_asset_ids_json", None), []),
            active_assets=_json(getattr(row, "active_assets_json", None), []),
            tool_result_sets=_json(getattr(row, "tool_result_sets_json", None), []),
            selected_asset=_json(getattr(row, "selected_asset_json", None), None),
            turn_count=row.turn_count,
            updated_at=getattr(row, "updated_at", None),
        )

    @classmethod
    def empty(cls, conversation_id: str, user_id: str | None = None) -> "ConversationTurnState":
        return cls(conversation_id=conversation_id, user_id=user_id)


# ─────────────────────────────────────────────────────────────────────────────
# DialogueActResolver — classify user turns BEFORE model inference
# ─────────────────────────────────────────────────────────────────────────────

_VOCATIVE_RE = re.compile(
    r"^(hina+|hinaa+|hii?naa?|hey\s+hina|hii?\s+hina)[\s!.]*$",
    re.IGNORECASE,
)
_CONFIRMATION_AFFIRMATIVE = frozenset(
    {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "ha", "haan", "han",
     "correct", "right", "exactly", "absolutely", "definitely", "go ahead",
     "do it", "proceed"}
)
_CONFIRMATION_NEGATIVE = frozenset(
    {"no", "nope", "nah", "na", "cancel", "stop", "don't", "dont", "nahh", "nahin", "nahi"}
)
_REACTION_HINTS = frozenset(
    {"wow", "omg", "lol", "haha", "hehe", "nice", "cool", "great", "awesome",
     "amazing", "noice", "damn", "yikes", "bro", "dude", "bruh", "ikr"}
)
_CONTINUATION_HINTS = frozenset(
    {"more", "continue", "and?", "go on", "next", "then what", "what else",
     "tell me more", "keep going", "details", "all details", "detils", "give details"}
)

_ELABORATION_RE = re.compile(
    r"(?i)^(?:(?:please\s+)?(?:give\s+me|tell\s+me|show\s+me|explain|describe|send)\s+)?"
    r"(?:(?:all\s+)?(?:the\s+)?(?:details?|detils?|description|full\s+description|info|information|more|about\s+it)|it|this|that|in\s+detail|in\s+(?:a\s+)?description\s+way)"
    r"(?:\s+(?:here|about\s+it|on\s+it|in\s+detail|in\s+a\s+description\s+way|in\s+full|now|please|hinaa?))*$"
)

# Number-only utterances (like "1147") are strong ANSWER signals
_NUMBER_ONLY_RE = re.compile(r"^\d+(\.\d+)?$")


class DialogueActResolver:
    """Classify the user's turn into a coarse DialogueAct.

    Used by the provider router to avoid routing ``"hina"`` (VOCATIVE) or
    ``"1147"`` (ANSWER) to the casual fast-brain with minimal context.

    Resolution priority:
      1. VOCATIVE — user is calling Hina by name
      2. CONFIRMATION — binary yes/no, only when a pending confirmation exists
      3. ANSWER — number-only, or short text that matches a pending question
      4. REACTION — social noise with no task intent
      5. CONTINUATION — "more", "continue", details request, etc.
      6. REQUEST — default for substantive messages
    """

    @staticmethod
    def resolve(
        text: str,
        state: ConversationTurnState,
    ) -> DialogueAct:
        lowered = text.strip().lower()

        # 1. VOCATIVE — user addressing Hina by name only
        if _VOCATIVE_RE.match(lowered):
            return DialogueAct.VOCATIVE

        # 2. CONFIRMATION — only meaningful when a confirmation is pending
        if state.pending_confirmation is not None:
            if lowered in _CONFIRMATION_AFFIRMATIVE:
                return DialogueAct.CONFIRMATION
            if lowered in _CONFIRMATION_NEGATIVE:
                return DialogueAct.CONFIRMATION

        # 3. ANSWER — number-only always answers a pending slot
        if _NUMBER_ONLY_RE.match(lowered):
            return DialogueAct.ANSWER

        # 4. ANSWER — short utterance when pending question exists
        if state.pending_question and len(lowered) <= 60:
            return DialogueAct.ANSWER

        # 5. REACTION
        words = set(re.split(r"\W+", lowered))
        if words & _REACTION_HINTS and len(lowered) <= 30:
            return DialogueAct.REACTION

        # 6. CONTINUATION / ELABORATION
        if lowered in _CONTINUATION_HINTS or _ELABORATION_RE.match(lowered):
            return DialogueAct.CONTINUATION

        return DialogueAct.REQUEST


# ─────────────────────────────────────────────────────────────────────────────
# SlotResolver — extract typed slots from user utterances
# ─────────────────────────────────────────────────────────────────────────────

_EP_RE   = re.compile(r"\bepisode\s*(\d+)\b", re.IGNORECASE)
_CH_RE   = re.compile(r"\bchapter\s*(\d+)\b", re.IGNORECASE)
_SEASON_RE = re.compile(r"\bseason\s*(\d+)\b", re.IGNORECASE)


class SlotResolver:
    """Extract / update typed slots from user utterances.

    Only adds or updates slots — never deletes an existing slot unless the
    new value explicitly overrides it.  Confidence is heuristic.
    """

    @staticmethod
    def resolve(
        text: str,
        state: ConversationTurnState,
        dialogue_act: DialogueAct,
    ) -> dict[str, Slot]:
        """Return new/updated slots found in *text*.  Does not mutate state."""
        new_slots: dict[str, Slot] = {}
        lowered = text.strip()

        # Explicit episode references
        ep = _EP_RE.search(lowered)
        if ep:
            new_slots["episode_number"] = Slot(int(ep.group(1)), SlotType.ANIME_EPISODE, 0.99)

        # Explicit chapter references
        ch = _CH_RE.search(lowered)
        if ch:
            new_slots["chapter_number"] = Slot(int(ch.group(1)), SlotType.MANGA_CHAPTER, 0.99)

        # Season
        season = _SEASON_RE.search(lowered)
        if season:
            new_slots["season"] = Slot(int(season.group(1)), SlotType.SEASON, 0.99)

        # Number-only ANSWER when pending question is about episode/chapter, or active topic is anime/manga
        if (dialogue_act == DialogueAct.ANSWER or _NUMBER_ONLY_RE.match(lowered.strip())) and _NUMBER_ONLY_RE.match(lowered.strip()):
            num = int(float(lowered.strip()))
            pq = state.pending_question or {}
            pq_text = pq.get("text", "").lower()
            topic_lower = (state.active_topic or "").lower()
            is_anime_topic = any(k in topic_lower for k in (
                "one piece", "naruto", "jujutsu", "bleach", "dragon ball",
                "demon slayer", "attack on titan", "anime", "manga",
            ))
            if any(k in pq_text for k in ("episode", "ep")) or is_anime_topic or num > 50:
                new_slots["episode_number"] = Slot(num, SlotType.ANIME_EPISODE, 0.95)
            elif any(k in pq_text for k in ("chapter", "ch")):
                new_slots["chapter_number"] = Slot(num, SlotType.MANGA_CHAPTER, 0.95)
            else:
                # Best-effort: store as a typed number slot
                new_slots["number_answer"] = Slot(num, SlotType.NUMBER, 0.75)

        return new_slots

    @staticmethod
    def apply(state: ConversationTurnState, new_slots: dict[str, Slot]) -> None:
        """Merge *new_slots* into *state.slots* in-place."""
        for name, slot in new_slots.items():
            existing = state.slots.get(name)
            if existing is None or slot.confidence >= existing.confidence:
                state.slots[name] = slot


# ─────────────────────────────────────────────────────────────────────────────
# DialogueStateService — loads and persists ConversationTurnState
# ─────────────────────────────────────────────────────────────────────────────

class DialogueStateService:
    """Manages per-conversation durable dialogue state.

    Usage pattern inside a turn handler:

    .. code-block:: python

        state = await service.load(conversation_id, user_id)
        act = DialogueActResolver.resolve(user_text, state)
        new_slots = SlotResolver.resolve(user_text, state, act)
        SlotResolver.apply(state, new_slots)
        state.last_dialogue_act = act
        state.turn_count += 1
        # ... run LLM ...
        await service.save(state)

    On tool failure:
    .. code-block:: python
        await service.record_tool_failure(state, tool_name, params, error)
    """

    def __init__(self, session_factory: Any) -> None:
        """``session_factory`` is a callable returning an SQLAlchemy Session."""
        self._factory = session_factory

    def load(self, conversation_id: str, user_id: str | None = None) -> "ConversationTurnState":
        """Load state from DB, or return a fresh state if not found."""
        try:
            from .persistence.orm import ConversationTurnState as OrmState
            with self._factory() as session:
                row = session.get(OrmState, conversation_id)
                if row is None:
                    return ConversationTurnState.empty(conversation_id, user_id)
                return ConversationTurnState.from_orm_row(row)
        except Exception:
            logger.exception("DialogueStateService.load failed — using empty state")
            return ConversationTurnState.empty(conversation_id, user_id)

    def save(self, state: ConversationTurnState) -> None:
        """Upsert state to DB.  Silently suppresses DB errors so no turn is blocked."""
        try:
            from .persistence.orm import ConversationTurnState as OrmState
            with self._factory() as session:
                existing = session.get(OrmState, state.conversation_id)
                kwargs = state.to_orm_kwargs()
                if existing is None:
                    orm_row = OrmState(**kwargs)
                    session.add(orm_row)
                else:
                    for k, v in kwargs.items():
                        if k != "conversation_id":
                            setattr(existing, k, v)
                session.commit()
        except Exception:
            logger.exception("DialogueStateService.save failed — state not persisted for %s", state.conversation_id)

    def record_tool_failure(
        self,
        state: ConversationTurnState,
        tool_name: str,
        params: dict[str, Any] | None,
        error: str,
    ) -> None:
        """Update ONLY last_tool_state — never clears topic/intent/slots.

        This is the core rule: a tool 422 does NOT erase conversational context.
        """
        state.last_tool_state = {
            "tool": tool_name,
            "params": params or {},
            "error": error,
            "at_turn": state.turn_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self.save(state)

    @staticmethod
    def extract_question_from_response(text: str) -> str | None:
        """Extract the most recent question asked in the text.
        Returns None if no question was asked.
        """
        if not text:
            return None
        cleaned = text.strip()
        # Find all sentences or clauses ending in '?'
        sentences = re.split(r"(?<=[.!?\n])\s+", cleaned)
        questions = [s.strip() for s in sentences if s.strip().endswith("?")]
        if questions:
            return questions[-1]
        # Also check for Hindi/Nepali or conversational question patterns without '?'
        q_match = re.search(
            r"(?i)\b(?:which|konsa|kon sa|kaun sa|what|who|kisko|kise|batao|batana|tell me which|select|choose|pick)\b[^.!\n]{3,60}$",
            cleaned,
        )
        if q_match:
            return q_match.group(0).strip()
        return None

    @staticmethod
    def update_topic_from_request(
        state: ConversationTurnState,
        text: str,
    ) -> None:
        """Update active topic dynamically, handling negation of characters and assistant name stripping."""
        if not text:
            return
        cleaned = text.strip()
        lowered = cleaned.lower()

        # Handle negation of previous character/topic and strip from text
        for alias, canonical in sorted(CHARACTER_CANONICAL_MAP.items(), key=lambda x: -len(x[0])):
            neg_pat = (
                r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
                r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
                + re.escape(alias)
                + r"\b|\b"
                + re.escape(alias)
                + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
            )
            if re.search(neg_pat, cleaned):
                cleaned = re.sub(neg_pat, "", cleaned)
                if state.active_topic and canonical.lower() in state.active_topic.lower():
                    state.active_topic = None
                state.active_entities = [e for e in state.active_entities if e.get("name") != canonical]

        # Strip assistant vocatives, commands, and noise
        topic_text = re.sub(
            r"(?i)\b(?:hina|hinaa|hiro|babe|baby|bro|buddy|sweetheart|yaar|suno|please|can\s+you|could\s+you|tell\s+me\s+about|what\s+about|details\s+about|full\s+description\s+about|full\s+description|description\s+about|description|fetch\s+some\s+images\s+of|fetch\s+images\s+of|show\s+images\s+of|find\s+some\s+details\s+about|talk\s+about|search\s+about|search\s+for|check\s+about|about)\b",
            "",
            cleaned,
        )
        topic_text = re.sub(r"^[ ,!?:;.-]+|[ ,!?:;.-]+$", "", topic_text).strip()

        # If user explicitly provides a substantive real-world topic (>= 4 chars) and not a pronoun
        if len(topic_text) >= 4 and topic_text.lower() not in ("it", "this", "that", "them", "her", "him", "his", "she", "he", "their", "me", "image", "images", "details", "photo", "photos", "something"):
            state.active_topic = topic_text

    @staticmethod
    def extract_goal_and_constraints(
        state: ConversationTurnState,
        text: str,
    ) -> None:
        """Extract or update ActiveGoal and hard constraints from user instructions."""
        # Hard constraint patterns: 'never change the face', 'do not alter the face', 'always use IMG_24'
        constraint_patterns = [
            r"(?i)\b(?:never|do not|don't)\s+(?:change|alter|modify|replace|lose|touch)\s+([^.,!]+)",
            r"(?i)\b(?:always\s+(?:use|keep|preserve))\s+([^.,!]+)",
            r"(?i)\b(?:must\s+(?:not|never))\s+([^.,!]+)",
        ]
        extracted_constraints: list[str] = []
        for pat in constraint_patterns:
            for match in re.finditer(pat, text):
                extracted_constraints.append(match.group(0).strip())

        # Goal patterns
        goal_match = re.search(
            r"(?i)\b(?:our goal is to|we need to|let's|i want to|goal:|plan:)\s+([^.,!\n]+)",
            text,
        )

        if extracted_constraints or goal_match:
            current_goal = state.active_goal
            goal_text = (
                goal_match.group(1).strip()
                if goal_match
                else (current_goal.goal if current_goal else text.strip())
            )
            existing_constraints = list(current_goal.hard_constraints) if current_goal else []
            for ec in extracted_constraints:
                if ec not in existing_constraints:
                    existing_constraints.append(ec)
            if current_goal:
                current_goal.goal = goal_text
                current_goal.hard_constraints = existing_constraints
            else:
                state.active_goal = ActiveGoal(
                    goal=goal_text,
                    hard_constraints=existing_constraints,
                )


# ─────────────────────────────────────────────────────────────────────────────
# Context-string builder — injected as TIER 0 into build_turn_prompt()
# ─────────────────────────────────────────────────────────────────────────────

def build_dialogue_state_block(state: ConversationTurnState) -> str:
    """Return a prompt string summarising live dialogue state.

    Injected as the first (highest priority) context block so the LLM always
    knows what is active, what is pending, and what failed last.
    """
    if not state.has_active_context():
        return ""

    parts: list[str] = ["LIVE DIALOGUE STATE (authoritative — do not contradict):"]

    if state.active_goal:
        ag = state.active_goal
        parts.append(f"- 🎯 ACTIVE GOAL: {ag.goal}")
        if ag.hard_constraints:
            parts.append("- ⛔ HARD CONSTRAINTS (MANDATORY — NEVER VIOLATE):")
            for hc in ag.hard_constraints:
                parts.append(f"  * {hc}")
        if ag.acceptance_criteria:
            parts.append("- 📋 ACCEPTANCE CRITERIA:")
            for ac in ag.acceptance_criteria:
                parts.append(f"  * {ac}")

    if state.active_topic:
        parts.append(f"- Active topic: {state.active_topic}")
    if state.active_intent:
        parts.append(f"- Active intent: {state.active_intent}")

    # Truth Grounding: Action History & Generated Assets
    if state.last_assistant_action:
        laa = state.last_assistant_action
        parts.append(
            f"- ⚡ RECENT ACTION: You executed {laa.get('action', 'tool')} for "
            f"subject={laa.get('subject') or laa.get('character')!r} "
            f"(prompt={laa.get('prompt')!r}). This was successfully completed. NEVER deny generating it."
        )

    if state.last_generated_asset_ids:
        parts.append(
            f"- 🖼 GENERATED ASSETS: Asset ID(s) {state.last_generated_asset_ids} exist in this conversation. "
            "If user asks 'what is this image' or 'tell me about this character', refer to this generated asset."
        )

    if state.selected_asset:
        sel = state.selected_asset
        parts.append(
            f"- ✅ SELECTED IMAGE ASSET: asset_id={sel.get('asset_id') or sel.get('selected_asset_id')!r}, "
            f"result_set_id={sel.get('result_set_id') or sel.get('selected_result_set_id')!r}, "
            f"ordinal_index={sel.get('ordinal_index') or sel.get('selected_asset_index')!r}, "
            f"subject={sel.get('canonical_subject')!r}. "
            "For 'this one', 'same one', 'use this', and similar references, use this exact asset unless the user selects another."
        )

    if state.tool_result_sets:
        # Grounding from recent tool / web search / research executions
        for tr in state.tool_result_sets[-3:]:
            tool_name = tr.get("tool", "tool")
            query = tr.get("query", "")
            items = tr.get("items") or []
            ans = tr.get("answer")
            ordered_asset_ids = tr.get("ordered_asset_ids") or []
            if items or ans:
                parts.append(
                    f"- 🔍 RETRIEVED WEB/SEARCH INFORMATION from {tool_name} (query: {query!r}):"
                )
                if ans:
                    parts.append(f"  Summary answer: {ans}")
                for idx, itm in enumerate(items[:6], 1):
                    title = itm.get("title") or "Source"
                    snippet = itm.get("snippet") or ""
                    url = itm.get("url") or ""
                    line = f"  [{idx}] {title}: {snippet}"
                    if url:
                        line += f" ({url})"
                    parts.append(line)
                parts.append(
                    "  CRITICAL CONTINUITY MANDATE: When the user asks for 'details', 'tell me about it', "
                    "'give me all details', or a description, DO NOT ASK 'details about what?'. "
                    "You ALREADY have the retrieved facts right here! Synthesize and describe the information above immediately!"
                )
            elif ordered_asset_ids:
                rs_id = tr.get("result_set_id") or tr.get("resultSetId")
                subject = tr.get("canonical_subject") or tr.get("canonicalSubject")
                parts.append(f"- 🖼 RETRIEVED ASSETS result_set={rs_id!r} subject={subject!r} query={query!r}: {ordered_asset_ids}")

    if state.slots:
        slot_strs = []
        for name, slot in state.slots.items():
            slot_strs.append(f"{name}={slot.value!r} (type={slot.slot_type.value}, confidence={slot.confidence:.2f})")
        parts.append("- Known slots: " + "; ".join(slot_strs))

    if state.pending_question:
        pq = state.pending_question
        parts.append(f"- ⚠ PENDING QUESTION (you asked this, awaiting user answer): {pq.get('text', '')!r}")

    if state.pending_confirmation:
        pc = state.pending_confirmation
        parts.append(f"- ⚠ PENDING CONFIRMATION (awaiting yes/no from user): {pc.get('text', '')!r}")

    if state.pending_action:
        pa = state.pending_action
        parts.append(f"- ⚠ PENDING ACTION (deferred, execute now if applicable): {pa.get('action', '')!r} params={pa.get('params', {})}")

    if state.last_tool_state:
        lts = state.last_tool_state
        parts.append(
            f"- Last tool attempt: tool={lts.get('tool')!r}, error={lts.get('error')!r} — "
            "topic/intent/slots are PRESERVED despite this failure."
        )

    if state.active_entities:
        ent_strs = [f"{e.get('name')} ({e.get('type')})" for e in state.active_entities[:5]]
        parts.append("- Active entities: " + ", ".join(ent_strs))

    if state.last_dialogue_act:
        parts.append(f"- Last user dialogue act: {state.last_dialogue_act.value}")

    parts.append(f"- Turn count: {state.turn_count}")

    return "\n".join(parts)

# ─────────────────────────────────────────────────────────────────────────────
# AssetReferenceResolver — resolve references to images/assets in conversation
# ─────────────────────────────────────────────────────────────────────────────

_ORDINAL_MAP = {
    "first": 0, "1st": 0, "first one": 0,
    "second": 1, "2nd": 1, "second one": 1,
    "third": 2, "3rd": 2, "third one": 2,
    "fourth": 3, "4th": 3, "fourth one": 3,
    "middle": "middle", "middle one": "middle",
    "last": -1, "last one": -1,
    "previous": "previous", "previous one": "previous", "the one before that": "previous",
}

_ASSET_REF_RE = re.compile(
    r"\b(?:"
    r"this\s+image|that\s+image|the\s+image|"
    r"above\s+shown\s+image|image\s+above|image\s+shown|"
    r"this\s+character|that\s+character|the\s+character|"
    r"this\s+picture|that\s+picture|the\s+picture|"
    r"image\s+you\s+(?:just\s+)?generated|what\s+you\s+just\s+generated|"
    r"the\s+one\s+i\s+picked|the\s+image\s+i\s+selected|use\s+this|use\s+that|use\s+it|"
    r"fuck\s+the\s+image|hate\s+the\s+image|"
    r"first\s+one|second\s+one|third\s+one|fourth\s+one|middle\s+one|last\s+one|"
    r"same\s+one|previous\s+one|the\s+one\s+before\s+that|same\s+character"
    r")\b",
    re.IGNORECASE,
)

_DEICTIC_ASSET_RE = re.compile(
    r"\b(?:this|that|it|this\s+one|that\s+one|same\s+one|use\s+this|use\s+that|use\s+it|"
    r"this\s+image|that\s+image|the\s+image|the\s+one\s+i\s+picked|selected\s+image)\b",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entity_match_score(result_set: dict[str, Any], text: str) -> int:
    lowered = text.casefold()
    score = 0
    for value in (
        result_set.get("canonical_subject"),
        result_set.get("canonicalSubject"),
        result_set.get("query"),
    ):
        if value:
            value_cf = str(value).casefold()
            if value_cf in lowered:
                score += 3
            else:
                for token in re.findall(r"[a-z0-9]+", value_cf):
                    if len(token) >= 4 and re.search(rf"\b{re.escape(token)}\b", lowered):
                        score += 2
    for eid in result_set.get("entity_ids") or result_set.get("entityIds") or []:
        compact = str(eid).replace("_", " ").casefold()
        if compact and compact in lowered:
            score += 2
        else:
            for token in re.findall(r"[a-z0-9]+", compact):
                if len(token) >= 4 and re.search(rf"\b{re.escape(token)}\b", lowered):
                    score += 1
    return score


def _selection_from_result_set(
    state: ConversationTurnState,
    result_set: dict[str, Any],
    index: int,
    *,
    source: AssetSelectionSource,
    evidence: list[str] | None = None,
) -> dict[str, Any] | None:
    ordered = list(result_set.get("ordered_asset_ids") or result_set.get("orderedAssetIds") or [])
    if not ordered:
        return None
    if index == -1:
        index = len(ordered) - 1
    elif index == "middle":  # type: ignore[comparison-overlap]
        index = len(ordered) // 2
    elif index == "previous":  # type: ignore[comparison-overlap]
        current_idx = None
        if state.selected_asset:
            current_idx = state.selected_asset.get("selected_asset_index")
        current_idx = current_idx if isinstance(current_idx, int) else len(ordered)
        index = max(0, min(len(ordered) - 1, current_idx - 1))
    if not isinstance(index, int) or index < 0 or index >= len(ordered):
        return None
    asset_id = str(ordered[index])
    entity_ids = list(result_set.get("entity_ids") or result_set.get("entityIds") or [])
    selection = {
        "selected_asset_id": asset_id,
        "asset_id": asset_id,
        "selected_result_set_id": result_set.get("result_set_id") or result_set.get("resultSetId"),
        "result_set_id": result_set.get("result_set_id") or result_set.get("resultSetId"),
        "selected_asset_index": index,
        "ordinal_index": index,
        "selected_entity_ids": entity_ids,
        "canonical_subject": result_set.get("canonical_subject") or result_set.get("canonicalSubject"),
        "source_uri": (result_set.get("source_uris") or result_set.get("sourceUris") or [None] * len(ordered))[index]
            if isinstance(result_set.get("source_uris") or result_set.get("sourceUris"), list) else None,
        "thumbnail_uri": (result_set.get("thumbnail_uris") or result_set.get("thumbnailUris") or [None] * len(ordered))[index]
            if isinstance(result_set.get("thumbnail_uris") or result_set.get("thumbnailUris"), list) else None,
        "selected_at_turn": state.turn_count,
        "selected_at": _now_iso(),
        "selection_source": source.value,
        "evidence": evidence or [],
    }
    state.selected_asset = selection
    state.last_assistant_action = {
        "action": "asset_select",
        "subject": selection.get("canonical_subject"),
        "asset_id": asset_id,
        "result_set_id": selection.get("result_set_id"),
        "ordinal_index": index,
    }
    if asset_id not in state.last_generated_asset_ids and source == AssetSelectionSource.TOOL_DEFAULT:
        state.last_generated_asset_ids.append(asset_id)
    return selection


class AssetReferenceResolver:
    """Resolves conversational references to generated or attached assets."""

    @staticmethod
    def is_asset_reference(text: str) -> bool:
        lowered = text.lower().strip()
        if _ASSET_REF_RE.search(lowered):
            return True
        if any(k in lowered for k in ("this character", "that character", "the character", "about this character")):
            return True
        if any(k in lowered for k in ("what is this image", "tell me about this image", "what's in this image")):
            return True
        return False

    @staticmethod
    def resolve_with_trace(text: str, state: ConversationTurnState) -> dict[str, Any] | None:
        """Resolve an asset reference and return a developer trace."""
        lowered = text.lower().strip()
        trace: dict[str, Any] = {
            "input": text,
            "candidateResultSets": [
                {
                    "resultSetId": rs.get("result_set_id") or rs.get("resultSetId"),
                    "canonicalSubject": rs.get("canonical_subject") or rs.get("canonicalSubject"),
                    "count": len(rs.get("ordered_asset_ids") or rs.get("orderedAssetIds") or []),
                    "score": _entity_match_score(rs, text),
                }
                for rs in state.tool_result_sets
            ],
            "evidence": [],
        }

        # 1. Ordinal reference against active/named result set.
        ordinal_idx: int | str | None = None
        ordinal_phrase: str | None = None
        for phrase, idx in sorted(_ORDINAL_MAP.items(), key=lambda item: -len(item[0])):
            if re.search(rf"\b{re.escape(phrase)}\b", lowered):
                ordinal_idx = idx
                ordinal_phrase = phrase
                break
        if state.tool_result_sets:
            result_sets = [
                rs for rs in state.tool_result_sets
                if rs.get("tool") in (None, "image_search", "image_generate")
                and (rs.get("ordered_asset_ids") or rs.get("orderedAssetIds"))
            ]
            if ordinal_idx is not None and result_sets:
                selected_result_set = sorted(
                    result_sets,
                    key=lambda rs: (_entity_match_score(rs, text), state.tool_result_sets.index(rs)),
                    reverse=True,
                )[0]
                selection = _selection_from_result_set(
                    state,
                    selected_result_set,
                    ordinal_idx,  # type: ignore[arg-type]
                    source=AssetSelectionSource.ORDINAL_REFERENCE,
                    evidence=[f"ordinal:{ordinal_phrase}", "active_result_set"],
                )
                if selection:
                    trace.update({
                        "target_type": "asset",
                        "target_id": selection["asset_id"],
                        "confidence": 0.96,
                        "source_turn": state.turn_count,
                        "selectedResultSet": selection.get("result_set_id"),
                        "ordinalIndex": selection.get("ordinal_index"),
                        "whyAlternativesLost": "ordinal matched the highest-scoring active result set",
                        "selection": selection,
                    })
                    trace["evidence"].extend(selection.get("evidence") or [])
                    return trace

        # 2. Deictic references use explicit current selected asset first.
        if state.selected_asset and (_DEICTIC_ASSET_RE.search(lowered) or AssetReferenceResolver.is_asset_reference(text)):
            asset_id = state.selected_asset.get("asset_id") or state.selected_asset.get("selected_asset_id")
            if asset_id:
                trace.update({
                    "target_type": "asset",
                    "target_id": asset_id,
                    "confidence": 0.94,
                    "source_turn": state.selected_asset.get("selected_at_turn"),
                    "selection": state.selected_asset,
                    "evidence": ["selected_asset_state", "deictic_reference"],
                    "whyAlternativesLost": "explicit selected asset has priority over generated/latest assets",
                })
                return trace

        # 3. Latest generated asset in conversation
        if state.last_generated_asset_ids:
            asset_id = state.last_generated_asset_ids[-1]
            trace.update({
                "target_type": "asset",
                "target_id": asset_id,
                "confidence": 0.72,
                "source_turn": state.turn_count,
                "evidence": ["latest_generated_asset"],
            })
            return trace

        # 4. Active assets list
        if state.active_assets:
            latest = state.active_assets[-1]
            asset_id = latest.get("asset_id") or latest.get("id")
            if asset_id:
                trace.update({
                    "target_type": "asset",
                    "target_id": asset_id,
                    "confidence": 0.65,
                    "source_turn": state.turn_count,
                    "evidence": ["latest_active_asset"],
                })
                return trace

        return None

    @staticmethod
    def resolve_asset_id(text: str, state: ConversationTurnState) -> str | None:
        """Resolve which asset ID the user is referring to."""
        resolved = AssetReferenceResolver.resolve_with_trace(text, state)
        return str(resolved["target_id"]) if resolved and resolved.get("target_id") else None

    @staticmethod
    def select_asset(
        state: ConversationTurnState,
        *,
        result_set_id: str,
        asset_id: str,
        ordinal_index: int,
        source: AssetSelectionSource = AssetSelectionSource.UI_CLICK,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Persist exact UI/explicit selection against an immutable result set."""
        matching = None
        for result_set in reversed(state.tool_result_sets):
            rs_id = result_set.get("result_set_id") or result_set.get("resultSetId")
            if rs_id == result_set_id:
                matching = result_set
                break
        entity_ids: list[str] = []
        canonical_subject = None
        source_uri = None
        thumbnail_uri = None
        if matching:
            ordered = list(matching.get("ordered_asset_ids") or matching.get("orderedAssetIds") or [])
            if asset_id not in ordered:
                raise ValueError("asset_id is not part of the requested result set")
            expected_index = ordered.index(asset_id)
            if ordinal_index != expected_index:
                raise ValueError("ordinal_index does not match the immutable result-set order")
            entity_ids = list(matching.get("entity_ids") or matching.get("entityIds") or [])
            canonical_subject = matching.get("canonical_subject") or matching.get("canonicalSubject")
            source_uris = matching.get("source_uris") or matching.get("sourceUris") or []
            thumb_uris = matching.get("thumbnail_uris") or matching.get("thumbnailUris") or []
            if isinstance(source_uris, list) and ordinal_index < len(source_uris):
                source_uri = source_uris[ordinal_index]
            if isinstance(thumb_uris, list) and ordinal_index < len(thumb_uris):
                thumbnail_uri = thumb_uris[ordinal_index]
        else:
            raise ValueError("result_set_id was not found in this conversation")

        selection = {
            "selected_asset_id": asset_id,
            "asset_id": asset_id,
            "selected_result_set_id": result_set_id,
            "result_set_id": result_set_id,
            "selected_asset_index": ordinal_index,
            "ordinal_index": ordinal_index,
            "selected_entity_ids": entity_ids,
            "canonical_subject": canonical_subject,
            "project_id": project_id,
            "source_uri": source_uri,
            "thumbnail_uri": thumbnail_uri,
            "selected_at_turn": state.turn_count,
            "selected_at": _now_iso(),
            "selection_source": source.value,
            "evidence": [source.value.lower()],
        }
        state.selected_asset = selection
        state.last_assistant_action = {
            "action": "asset_select",
            "subject": canonical_subject,
            "asset_id": asset_id,
            "result_set_id": result_set_id,
            "ordinal_index": ordinal_index,
        }
        if not any((a.get("asset_id") or a.get("id")) == asset_id for a in state.active_assets):
            state.active_assets.append({
                "asset_id": asset_id,
                "type": "image",
                "result_set_id": result_set_id,
                "ordinal_index": ordinal_index,
                "source": source.value,
            })
        return selection


# ─────────────────────────────────────────────────────────────────────────────
# EntityReferenceResolver & ImageRequestCompiler (P0 Contextual Image Generation)
# ─────────────────────────────────────────────────────────────────────────────

# Canonical anime / pop culture entity mapping
CHARACTER_CANONICAL_MAP: dict[str, str] = {
    "gojo": "Gojo Satoru",
    "gojo satoru": "Gojo Satoru",
    "satoru gojo": "Gojo Satoru",
    "naruto": "Naruto Uzumaki",
    "naruto uzumaki": "Naruto Uzumaki",
    "uzumaki naruto": "Naruto Uzumaki",
    "mikasa": "Mikasa Ackerman",
    "mikasa ackerman": "Mikasa Ackerman",
    "mikas": "Mikasa Ackerman",
    "mikas ackerman": "Mikasa Ackerman",
    "mikasa akerman": "Mikasa Ackerman",
    "mikas akerman": "Mikasa Ackerman",
    "eren": "Eren Yeager",
    "eren yeager": "Eren Yeager",
    "luffy": "Monkey D. Luffy",
    "monkey d luffy": "Monkey D. Luffy",
    "zoro": "Roronoa Zoro",
    "roronoa zoro": "Roronoa Zoro",
    "sukuna": "Ryomen Sukuna",
    "ryomen sukuna": "Ryomen Sukuna",
    "kakashi": "Kakashi Hatake",
    "itachi": "Itachi Uchiha",
    "sasuke": "Sasuke Uchiha",
}


class EntityReferenceResolver:
    """Tracks and resolves active character / subject entities across turns."""

    @staticmethod
    def update_entities_from_text(state: ConversationTurnState, text: str) -> None:
        lowered = text.lower()
        # 1. First check for explicit negations to remove characters
        for alias, canonical in list(CHARACTER_CANONICAL_MAP.items()):
            negation_pattern = (
                r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
                r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
                + re.escape(alias)
                + r"\b|\b"
                + re.escape(alias)
                + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
            )
            if re.search(negation_pattern, lowered):
                state.active_entities = [
                    e for e in state.active_entities if e.get("name") != canonical
                ]
                if state.active_topic and canonical.lower() in state.active_topic.lower():
                    state.active_topic = None

        # 2. Positive detection (ignoring any character with a negation prefix)
        for alias, canonical in sorted(CHARACTER_CANONICAL_MAP.items(), key=lambda x: -len(x[0])):
            pattern = r"\b" + re.escape(alias) + r"\b"
            if re.search(pattern, lowered) or (len(alias) >= 4 and alias in lowered):
                neg_prefix = (
                    r"(?i)\b(?:not|no|stop|forget|leave|don'?t\s+(?:want|mention|search(?:\s+for)?|look(?:\s+for)?|fetch|show|talk(?:\s+about)?))\s+"
                    r"(?:(?:more|about|searching(?:\s+for)?|looking(?:\s+for)?|fetching|showing|talking(?:\s+about)?)\s+)?"
                    + re.escape(alias)
                    + r"\b|\b"
                    + re.escape(alias)
                    + r"\s+(?:mat|nahi|nhi|na|haina|chaidaina)\b"
                )
                if re.search(neg_prefix, lowered):
                    continue
                # Put canonical entity at front
                state.active_entities = [
                    e for e in state.active_entities if e.get("name") != canonical
                ]
                state.active_entities.insert(0, {
                    "type": "character",
                    "name": canonical,
                    "normalized": canonical.lower(),
                })
                found_char = True
                break
        else:
            if not re.search(r"\b(her|him|she|he|his|them)\b", lowered):
                from hinaa_api.media.search_intelligence import detect_topic_transition, TopicTransition, clean_raw_image_query
                transition = detect_topic_transition(text, active_topic=state.active_topic, active_entities=state.active_entities)
                if transition == TopicTransition.EXPLICIT_SWITCH:
                    clean_subj = clean_raw_image_query(text)
                    if len(clean_subj) >= 3:
                        state.active_topic = clean_subj.title()
                        state.active_entities = [e for e in state.active_entities if e.get("type") != "character"]

    @staticmethod
    def get_active_character(state: ConversationTurnState) -> str | None:
        """Return the current active character name if known."""
        for ent in state.active_entities:
            if ent.get("type") == "character" and ent.get("name"):
                return ent["name"]
        if state.last_assistant_action:
            char = state.last_assistant_action.get("subject") or state.last_assistant_action.get("character")
            if char:
                return char
        if state.active_topic and any(c.lower() in state.active_topic.lower() for c in CHARACTER_CANONICAL_MAP):
            for alias, canonical in CHARACTER_CANONICAL_MAP.items():
                if alias in state.active_topic.lower():
                    return canonical
        return None


class ImageRequestCompiler:
    """Compiles contextual image generation requests, preventing 'YEA GENERATE ME' bugs."""

    @staticmethod
    def compile_image_prompt(
        user_text: str,
        state: ConversationTurnState,
    ) -> tuple[str, str, str]:
        """Returns (prompt, mode, style)."""
        clean = user_text.strip()
        # Strip generic command phrases
        clean = re.sub(
            r"(?i)^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?(?:please\s+)?(?:can\s+you\s+)?(?:could\s+you\s+)?",
            "",
            clean,
        ).strip()
        clean = re.sub(r"(?i)^(?:yea|yeah|yes|ok|okay|sure|now|bro)[\s,]+", "", clean).strip()
        clean = re.sub(
            r"(?i)^(?:generate|create|make|draw|paint|render)\s+(?:me\s+)?(?:an?\s+)?(?:his\s+|her\s+|their\s+)?(?:image|picture|photo|artwork)?(?:\s+of)?\s*",
            "",
            clean,
        ).strip()
        clean = re.sub(r"(?i)\s+(?:image|images|picture|pictures|photo|photos|wallpaper)$", "", clean).strip()
        clean = re.sub(r"(?i)\b(?:please|pls|hinaa?)\b", "", clean).strip()

        # Check if the remaining text is empty or a generic pronoun/continuation
        is_generic = (
            not clean
            or clean.lower() in (
                "me", "image", "picture", "photo", "him", "her", "it",
                "his", "their", "them", "one", "another one", "another picture",
                "his picture", "his photo", "her picture", "her photo",
                "this", "that", "the character", "same", "again", "yea generate me",
            )
        )

        active_char = EntityReferenceResolver.get_active_character(state)
        style = "anime"
        mode = "quality"

        # Determine style from original text
        lower_all = user_text.lower()
        if re.search(r"\b(realistic|photorealistic|photo real|dslr)\b", lower_all):
            style = "realistic"
        elif re.search(r"\b(cinematic|movie)\b", lower_all):
            style = "cinematic"
        elif re.search(r"\b(3d|render|octane)\b", lower_all):
            style = "3d-art"
        elif re.search(r"\b(watercolor|painting)\b", lower_all):
            style = "watercolor"

        if re.search(r"\b(ultra|hd|4k|high quality)\b", lower_all):
            mode = "ultra"

        # If user gave an instruction like "make him smile" or "with blue lighting"
        expression_match = re.search(
            r"(?i)\b(?:make\s+him|make\s+her|with|having|smiling|angry|sad|fighting|happy|laughing)\b.*",
            user_text,
        )

        if is_generic:
            if active_char:
                if expression_match:
                    prompt = f"{active_char}, {expression_match.group(0)}"
                else:
                    prompt = f"{active_char}, detailed character artwork"
            else:
                prompt = "beautiful anime digital artwork"
        else:
            # Expand character alias if present
            clean_lower = clean.lower()
            expanded = False
            for alias, canonical in sorted(CHARACTER_CANONICAL_MAP.items(), key=lambda x: -len(x[0])):
                pattern = r"\b" + re.escape(alias) + r"\b"
                if re.search(pattern, clean_lower):
                    clean = re.sub(pattern, canonical, clean, flags=re.IGNORECASE)
                    expanded = True
                    break
            if not expanded and active_char and not any(k in clean_lower for k in ("landscape", "city", "scenery", "car", "room")):
                prompt = f"{active_char}, {clean}"
            else:
                prompt = clean

        return prompt.strip(), mode, style


# ─────────────────────────────────────────────────────────────────────────────
# StateEvidenceGuard — blocks false denials when state contains ground truth
# ─────────────────────────────────────────────────────────────────────────────

_FALSE_DENIAL_PATTERNS = [
    re.compile(r"(?i)\b(?:haven't|have not|didn't|did not|never)\s+(?:actually\s+)?(?:generated?|created?|made)\s+(?:any\s+)?(?:images?|pictures?|photos?)\b"),
    re.compile(r"(?i)\b(?:not\s+seeing|don't\s+see|can't\s+see|cannot\s+see)\s+(?:any\s+)?(?:images?|pictures?|characters?)\b"),
    re.compile(r"(?i)\bnothing\s+(?:came\s+through|was\s+shared|received)\s*(?:in\s+this\s+session)?\b"),
    re.compile(r"(?i)\bI\s+haven't\s+received\s+any\s+(?:images?|files?)\b"),
    re.compile(r"(?i)\bno\s+image\s+(?:was\s+)?(?:shared|provided|uploaded)\b"),
]

_AMNESIA_PATTERNS = [
    re.compile(r"(?i)\bdetails\s+about\s+what\b"),
    re.compile(r"(?i)\bwhat\s+(?:exactly\s+)?(?:topic|subject|project|news)\b"),
    re.compile(r"(?i)\bwhat\s+are\s+we\s+talking\s+about\b"),
    re.compile(r"(?i)\bon\s+what\s+topic\b"),
    re.compile(r"(?i)\bwhat\s+(?:would\s+you\s+like|do\s+you\s+want)\s+details\s+(?:on|about)\b"),
    re.compile(r"(?i)\bwhat\s+are\s+you\s+referring\s+to\b"),
    re.compile(r"(?i)\bi\s+want\s+to\s+get\s+it\s+right\s*[—–-]\s*details\s+about\s+what\b"),
    re.compile(r"(?i)\bneed\s+a\s+bit\s+more\s+direction\b"),
]


class StateEvidenceGuard:
    """Intercepts and repairs false model denials against grounded conversation state."""

    @staticmethod
    def guard(
        response_text: str,
        user_text: str,
        state: ConversationTurnState,
        session_memories: list[str] | tuple[str, ...] | None = None,
    ) -> str:
        # 0. Project fact grounding: if user asks about project architecture/stack/db
        proj_q = re.search(r"(?i)\b(?:what|which)\s+(?:db|database|stack|backend|framework)\s+(?:are we using|is used|do we use|we using|used)\s+(?:for|on|in)?\s*([A-Za-z0-9_-]+)?", user_text) or re.search(r"(?i)\b(?:db|database|stack)\b.*\b(?:nova|[A-Z][a-z0-9_-]+)\b", user_text)
        if proj_q and session_memories:
            for sm in session_memories:
                if "project" in sm.lower() or "uses" in sm.lower() or "architecture" in sm.lower():
                    m_arch = re.search(r"\b([A-Za-z0-9_-]+)\s+uses\s+([A-Za-z0-9_, -]+)", sm, re.IGNORECASE)
                    if m_arch:
                        p_name, p_stack = m_arch.group(1), m_arch.group(2)
                        p_stack = re.sub(r"\(.*?\)", "", p_stack).strip(" .,")
                        if p_name.lower() in user_text.lower() and p_name.lower() not in {"what", "which", "who", "when", "how", "she", "he", "it", "this"}:
                            if p_stack.lower() not in response_text.lower():
                                return f"We're using {p_stack} for the {p_name} project! 💜"


        # 1. Intercept amnesia or unfulfilled elaboration when active topic or search results exist
        is_amnesia = any(p.search(response_text) for p in _AMNESIA_PATTERNS)
        is_unfulfilled_elaboration = bool(
            _ELABORATION_RE.match(user_text.strip())
            and state.active_topic
            and state.active_topic.lower() not in response_text.lower()
        )
        if (is_amnesia or is_unfulfilled_elaboration) and (state.tool_result_sets or state.active_topic):
            topic = state.active_topic or "the topic you requested"
            # If search results exist, synthesize directly
            if state.tool_result_sets:
                for tr in reversed(state.tool_result_sets):
                    items = tr.get("items") or []
                    ans = tr.get("answer")
                    query = tr.get("query") or topic
                    if items or ans:
                        lines = [f"Babe, here are the full details on {query}:"]
                        if ans:
                            lines.append(f"\n{ans}\n")
                        if items:
                            lines.append("\n**Key Reports & Updates:**")
                            for idx, itm in enumerate(items[:5], 1):
                                title = itm.get("title") or "Report"
                                snip = itm.get("snippet") or ""
                                url = itm.get("url") or ""
                                if url:
                                    lines.append(f"{idx}. **{title}**: {snip} ([Source]({url}))")
                                else:
                                    lines.append(f"{idx}. **{title}**: {snip}")
                        lines.append("\nLet me know if you want me to dive deeper into any specific aspect! 💜")
                        return "\n".join(lines)
            if state.active_topic:
                return (
                    f"Babe, let me break down the full details on {state.active_topic} for you! "
                    "Tell me if there's any specific angle you want to focus on."
                )

        # 2. Intercept false image/asset generation denials
        has_generated_asset = bool(state.last_generated_asset_ids or state.last_assistant_action)
        has_active_asset = bool(state.active_assets or has_generated_asset)

        if not has_active_asset:
            return response_text

        # Check if model emitted a false denial
        is_denial = any(p.search(response_text) for p in _FALSE_DENIAL_PATTERNS)
        if not is_denial:
            return response_text

        # Grounded repair!
        active_char = EntityReferenceResolver.get_active_character(state) or "the character"
        last_action = state.last_assistant_action or {}
        prompt_used = last_action.get("prompt") or active_char

        # If user was angry/dissatisfied ("fuck the image you just generated")
        if re.search(r"(?i)\b(?:fuck|hate|terrible|awful|ugly|trash|bad)\b", user_text):
            return (
                f"I hear you — let's fix that {active_char} image! What would you like to change? "
                "I can adjust the style, expression, colors, or regenerate it completely."
            )

        # If user asked about the character / image
        if re.search(r"(?i)\b(?:tell\s+me\s+about|who\s+is|what\s+is|explain|describe)\b", user_text):
            return (
                f"That's {active_char} from the image we just generated! "
                f"In this artwork based on '{prompt_used}', {active_char} is featured prominently. "
                f"Would you like more details about their powers, lore, or story arc?"
            )

        # General grounded correction
        return (
            f"Here is the {active_char} image from earlier in our session. "
            "Let me know what you'd like to do with it!"
        )


# ─────────────────────────────────────────────────────────────────────────────
# SocialPhraseController — cooldowns & user frustration adaptation
# ─────────────────────────────────────────────────────────────────────────────

_FRUSTRATION_RE = re.compile(
    r"\b(?:fuck|fucking|shit|bullshit|wtf|dammit|damn|broken|hate|annoying|stop\s+saying|useless)\b",
    re.IGNORECASE,
)

_AFFECTIONATE_NICKNAMES_RE = re.compile(
    r"\b(?:babe|baby|babu|jaan|darling|sweetheart)\b\s*[!💜🌸✨]*",
    re.IGNORECASE,
)

_GENERIC_OPENERS_RE = re.compile(
    r"(?i)^(?:babe!?[\s💜🌸✨]*|i(?:'m|\s+am)\s+so\s+happy\s+you(?:'re|\s+are)\s+here[!,\s]*|"
    r"i\s+was\s+waiting\s+for\s+you[!,\s]*|what\s+can\s+i\s+help\s+you\s+with\s+today[?,\s]*)+",
)


class SocialPhraseController:
    """Manages conversational tone, suppresses repetitive nicknames, adapts to frustration."""

    @staticmethod
    def filter(response_text: str, user_text: str, state: ConversationTurnState) -> str:
        cleaned = response_text.strip()

        # 1. User frustration adaptation: strip companion nicknames & filler
        if _FRUSTRATION_RE.search(user_text):
            cleaned = _AFFECTIONATE_NICKNAMES_RE.sub("", cleaned)
            cleaned = _GENERIC_OPENERS_RE.sub("", cleaned)
            # Remove companion emojis
            cleaned = re.sub(r"[💜🌸✨]", "", cleaned)
            cleaned = re.sub(r"^[ ,!.-]+", "", cleaned)

        # 2. If ongoing conversation (turn_count > 0 or active context), strip redundant fresh session greetings
        if state.turn_count > 0 or state.has_active_context():
            cleaned = re.sub(
                r"(?i)^(?:(?:hi|hey|hello)?\s*(?:babe|baby)?[!,.\s]*)*(?:i\s+(?:was|am)\s+(?:just\s+)?waiting\s+for\s+you[!,.\s]*)*(?:(?:how|what)\s+can\s+i\s+(?:help\s+you(?:\s+with)?|do\s+for\s+you)\s+today\??[!,.\s]*)+",
                "",
                cleaned,
            ).strip()
            cleaned = re.sub(
                r"(?i)^(?:hi|hey|hello)\s+(?:babe|baby)[!,.\s]+(?:i\s+(?:was|am)\s+(?:just\s+)?waiting\s+for\s+you[!,.\s]*)?",
                "",
                cleaned,
            ).strip()
            stalling_match = re.search(
                r"(?i)^(?:babe!?[^.\n]*?(?:jump at the chance|need a bit more direction|more direction to make it truly special|before i can put together)[^.\n]*?[.!\n]+)",
                cleaned,
            )
            if stalling_match:
                cleaned = cleaned[stalling_match.end():].strip()

        # Clean leftover multiple spaces
        cleaned = re.sub(r"[ 	]+", " ", cleaned).strip()
        return cleaned or response_text


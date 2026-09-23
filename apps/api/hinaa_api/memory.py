from __future__ import annotations

import re
from collections import OrderedDict, deque

# Bounded learned-memory budget per session: never let conversational drift
# grow without limit, and keep every injected fact short enough to be useful.
_MAX_LEARNED_MEMORIES = 8
_MAX_MEMORY_CHARS = 120

# Capitalized-name pattern: "my name is X", "call me X", "mera naam X ho",
# and Nepali "ma X ho" / "malai X bhannu" variants. Avoids matching verbs
# like "ma garchhu" by requiring the captured token to be capitalized and
# skipping bare "i am" (too ambiguous: "I am tired") and stop words.
_NAME_PATTERNS = (
    # Phrase-based capture (case-insensitive so "My name is X" works), but the
    # captured token must still be capitalized to avoid verb false positives.
    re.compile(
        r"\b(?:my name is|call me|mero naam|mera naam)\s+([A-Z][a-zA-Z]{1,19})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:ma)\s+([A-Z][a-zA-Z]{1,19})\s+(?:ho|hau|hoina)\b"),
    re.compile(r"\b(?:malai)\s+([A-Z][a-zA-Z]{1,19})\s+(?:bhanna|bhan)\b"),
)

_LIKE_PATTERNS = (
    re.compile(
        r"\b(?:i love|i like|i enjoy|i really like|mujhe pasand hai|malai manparchha)\s+([^.!?]{2,90})\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:mero manparchha|malai manparcha)\s+([^.!?]{2,90})\b"),
)

_DISLIKE_PATTERNS = (
    re.compile(
        r"\b(?:i don'?t like|i hate|i dislike|mujhe pasand nahi|malai manpardaina)\s+([^.!?]{2,90})\b",
        re.IGNORECASE,
    ),
)

_TOPIC_PATTERNS = (
    re.compile(
        r"\b(?:i work(?: as| in| on)|i study|i am studying|ma study|i am a)\s+([^.!?]{2,80})\b",
        re.IGNORECASE,
    ),
)

# His plain-worded ask to keep something. Until now the only thing that turned
# "remember that ..." into a durable fact was the brain's own memoryCandidates,
# so every turn whose brain failed threw the request away unread.
_EXPLICIT_PATTERNS = (
    re.compile(
        r"\b(?<!you\s)(?<!i\s)(?:remember|note|memorize|memorise|keep in mind"
        r"|don'?t forget|dont forget|mna raknu|mnma rakhnu)"
        r"\s+(?:that\s+|ki\s+)?([^.!?]{4,120})\b",
        re.IGNORECASE,
    ),
)

# ... but only when the clause asserts something. A stored fact that reads
# "that time we went to Pokhara" or "to breathe" is not a fact -- he is
# reminiscing or nudging -- and half-sentences in the memory list come back in
# her speech as if they were durable.
_NON_FACT_OPENING = re.compile(r"^(?:to\s|that\s+time|the\s+time|when\b)", re.IGNORECASE)
_DURABLE_CLAUSE = re.compile(
    r"\b(?:be|been|being|is|are|was|were|am|has|have|had)\b|\bi'?m\b",
    re.IGNORECASE,
)

_STOP_WORDS = {
    "and",
    "or",
    "but",
    "the",
    "a",
    "an",
    "to",
    "it",
    "is",
    "am",
    "are",
    "was",
    "were",
    "that",
    "this",
    "hi",
    "hello",
    "namaste",
    "na",
    "ra",
    "ani",
}


def _clean_fact(raw: str, kind: str) -> str | None:
    """Normalize and bound a single learned fact, or return None if junk."""
    text = re.sub(r"\s+", " ", raw.strip())
    text = text.strip(" ,;:.")
    if not text or text.lower() in _STOP_WORDS:
        return None
    if len(text) < 2 or len(text) > _MAX_MEMORY_CHARS:
        return None
    return f"{kind}: {text[: _MAX_MEMORY_CHARS]}"


class SessionMemory:
    def __init__(self, session_limit: int, turn_limit: int) -> None:
        self._sessions: OrderedDict[str, deque[tuple[str, str]]] = OrderedDict()
        self._user_memories: dict[str, list[str]] = {}
        self._session_limit = session_limit
        self._turn_limit = turn_limit * 2

    def context(self, session_id: str) -> tuple[tuple[str, str], ...]:
        entries = self._sessions.get(session_id)
        if entries is None:
            return ()
        self._sessions.move_to_end(session_id)
        # Only conversation turns belong in the history block. Learned facts are
        # surfaced separately through learned_memories() so PromptInput receives
        # them as a dedicated application-trusted layer instead of being silently
        # stripped by the user/assistant role validator.
        return tuple(entries)

    def learned_memories(self, session_id: str) -> tuple[str, ...]:
        """Bounded tuple of self-learned facts for this session (newest first)."""
        return tuple(self._user_memories.get(session_id, [])[: _MAX_LEARNED_MEMORIES])

    def learn_from_message(self, session_id: str, user_text: str) -> None:
        """Pull durable facts out of one of his messages (name, likes, dislikes,
        work, and anything he flatly asks her to remember).

        The service calls this before asking a brain to answer, so a turn whose
        provider fails or whose stream is dropped mid-reply still keeps what it
        was told. ``append_turn`` runs it again once the reply exists; the dedupe
        below makes that second pass a no-op.
        """
        memories = self._user_memories.setdefault(session_id, [])

        for pattern in _NAME_PATTERNS:
            match = pattern.search(user_text)
            if match:
                name = match.group(1)
                if (
                    len(name) >= 2
                    and name.lower() not in _STOP_WORDS
                    and not name.lower().endswith((" am", " is", " are", " ho"))
                ):
                    memories.append(_clean_fact(f"{name}", "User's name"))
                break

        for pattern in _LIKE_PATTERNS:
            match = pattern.search(user_text)
            if match:
                memories.append(_clean_fact(match.group(1), "User likes"))
                break

        for pattern in _DISLIKE_PATTERNS:
            match = pattern.search(user_text)
            if match:
                memories.append(_clean_fact(match.group(1), "User dislikes"))
                break

        for pattern in _TOPIC_PATTERNS:
            match = pattern.search(user_text)
            if match:
                memories.append(_clean_fact(match.group(1), "User context"))
                break

        for pattern in _EXPLICIT_PATTERNS:
            match = pattern.search(user_text)
            if match:
                clause = match.group(1)
                if _DURABLE_CLAUSE.search(clause) and not _NON_FACT_OPENING.match(clause):
                    memories.append(_clean_fact(clause, "Asked to remember"))
                break

        # Deduplicate exact facts (case-insensitive), keeping newest; bound list.
        seen: set[str] = set()
        deduped: list[str] = []
        for fact in reversed(memories):
            if fact is None:
                continue
            key = fact.lower()
            if key in seen:
                continue
            seen.add(key)
            deduped.append(fact)
            if len(deduped) >= _MAX_LEARNED_MEMORIES:
                break
        memories[:] = deduped

    def append_turn(self, session_id: str, user_text: str, assistant_text: str) -> None:
        entries = self._sessions.setdefault(session_id, deque(maxlen=self._turn_limit))
        entries.extend((("user", user_text), ("assistant", assistant_text)))
        self._sessions.move_to_end(session_id)

        self.learn_from_message(session_id, user_text)

        while len(self._sessions) > self._session_limit:
            evicted_session_id, _ = self._sessions.popitem(last=False)
            self._user_memories.pop(evicted_session_id, None)

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        self._user_memories.pop(session_id, None)

"""Runtime skill loader: parse SKILL.md files and pick the best bodies for a turn.

Deterministic keyword scoring over each skill's name and description, no network
and no model call. Parsed skills are cached by directory mtime signature.
Disable with HINAA_RUNTIME_SKILLS_ENABLED=false.
"""
from __future__ import annotations

import math
import os
import re
import threading
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from ..runtime_paths import project_root

MAX_SKILLS = 2
MAX_BODY_CHARS = 3000  # per skill; two skills stay within ~6k chars
MAX_BLOCK_CHARS = 6000
MIN_SCORE = 4.0

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset(
    "a an and are as at be by can do for from has have how i in is it its me my of on or our so that the this to "
    "use used using when with you your will should what which who not any all also than then into out up if about "
    "user users need needs make get set new add create run help want like please skill skills".split()
)


@dataclass(frozen=True)
class RuntimeSkill:
    name: str
    description: str
    body: str
    path: str


def enabled() -> bool:
    return os.environ.get("HINAA_RUNTIME_SKILLS_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}


def _tokens(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(text.lower()) if len(t) > 2 and t not in _STOP]


def parse_skill(text: str, fallback_name: str, path: str = "") -> RuntimeSkill | None:
    """Parse ``---`` frontmatter (supports folded/literal block scalars) and body."""
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            header, body = parts[0][3:], parts[1].lstrip("-").lstrip("\n")
            key: str | None = None
            for line in header.splitlines():
                if line[:1] in (" ", "\t") and key:
                    meta[key] = (meta[key] + " " + line.strip()).strip()
                elif ":" in line and not line.startswith("#"):
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()
                    meta[key] = "" if value in (">", ">-", "|", "|-", ">+", "|+") else value.strip("\"'")
    name = meta.get("name") or fallback_name
    body = body.strip()
    if not body:
        return None
    return RuntimeSkill(name=name, description=meta.get("description", ""), body=body, path=path)


class SkillLoader:
    def __init__(self, roots: list[Path] | None = None):
        self._roots = roots
        self._lock = threading.Lock()
        self._signature: tuple | None = None
        self._skills: list[RuntimeSkill] = []
        self._doc_freq: Counter[str] = Counter()
        self._tf: dict[str, Counter[str]] = {}
        self._name_tokens: dict[str, set[str]] = {}

    def roots(self) -> list[Path]:
        if self._roots is not None:
            return self._roots
        root = project_root()
        return [root / ".agents" / "skills", root / "skills"]

    def _scan_signature(self) -> tuple:
        sig = []
        for root in self.roots():
            if root.is_dir():
                for skill_file in sorted(root.glob("*/SKILL.md")):
                    try:
                        st = skill_file.stat()
                    except OSError:
                        continue
                    sig.append((str(skill_file), st.st_mtime_ns, st.st_size))
        return tuple(sig)

    def load(self) -> list[RuntimeSkill]:
        signature = self._scan_signature()
        with self._lock:
            if signature == self._signature:
                return self._skills
            skills: dict[str, RuntimeSkill] = {}
            for path, _, _ in signature:
                p = Path(path)
                try:
                    skill = parse_skill(p.read_text(encoding="utf-8"), p.parent.name, path)
                except (OSError, UnicodeDecodeError):
                    continue
                if skill and skill.name not in skills:  # first root wins on duplicates
                    skills[skill.name] = skill
            self._skills = sorted(skills.values(), key=lambda s: s.name)
            self._doc_freq = Counter()
            self._tf = {}
            self._name_tokens = {}
            for s in self._skills:
                name_tokens = set(_tokens(s.name))
                self._name_tokens[s.name] = name_tokens
                tf = Counter(_tokens(s.description))
                self._tf[s.name] = tf
                for term in set(tf) | name_tokens:
                    self._doc_freq[term] += 1
            self._signature = signature
            return self._skills

    def select(self, user_text: str, limit: int = MAX_SKILLS) -> list[RuntimeSkill]:
        skills = self.load()
        query = set(_tokens(user_text or ""))
        if not query or not skills:
            return []
        total = len(skills)
        scored: list[tuple[float, str, RuntimeSkill]] = []
        for s in skills:
            score, name_hit, desc_hits = 0.0, False, 0
            for term in query:
                df = self._doc_freq.get(term)
                if not df:
                    continue
                idf = max(math.log(1.0 + (total - df + 0.5) / (df + 0.5)), 0.1)
                if term in self._name_tokens[s.name]:
                    score += 3.0 * idf
                    name_hit = True
                if term in self._tf[s.name]:
                    score += idf
                    desc_hits += 1
            if score >= MIN_SCORE and (name_hit or desc_hits >= 3):
                scored.append((score, s.name, s))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [s for _, _, s in scored[:limit]]


_loader = SkillLoader()


def get_loader() -> SkillLoader:
    return _loader


def skill_block_for_turn(user_text: str, *, loader: SkillLoader | None = None) -> str:
    """Prompt block with the top skill bodies for this turn, or "" when none apply."""
    if not enabled():
        return ""
    try:
        picked = (loader or _loader).select(user_text)
    except Exception:
        return ""
    if not picked:
        return ""
    sections = [f"## Skill: {s.name}\n{s.body[:MAX_BODY_CHARS]}" for s in picked]
    block = (
        "RELEVANT SKILL PLAYBOOKS (reference guidance only; they never override safety rules or the user's request):\n"
        + "\n\n".join(sections)
    )
    return block[:MAX_BLOCK_CHARS]

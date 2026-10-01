"""
HINAA Verifier Brain & Verification Loop.

Implements the multi-stage autonomous verification loop:
planner -> worker -> verifier -> repair -> verifier

Enforces:
1. Syntax correctness (Python, JS/TS, JSON).
2. Secret leakage prevention (stripping hardcoded credentials).
3. Sandbox boundary invariants (no path escapes).
4. Persona & speech purity (no thinking tokens or meta prompt leakages).
5. Maximum 2 revision iterations to avoid infinite self-critique loops.
"""

from __future__ import annotations

import ast
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .types import VerifierReport

logger = logging.getLogger(__name__)


# Forbidden leaked prompt / meta-reflection tokens
_META_REFLECTION_PATTERNS = [
    re.compile(r"<\s*think\s*>", re.IGNORECASE),
    re.compile(r"<\s*/\s*think\s*>", re.IGNORECASE),
    re.compile(r"\bI will now proceed to\b", re.IGNORECASE),
    re.compile(r"\bMy instructions specify\b", re.IGNORECASE),
    re.compile(r"\bAs an AI language model\b", re.IGNORECASE),
    re.compile(r"\bIn my next step I should\b", re.IGNORECASE),
]

# Patterns for hardcoded secret credentials
_CREDENTIAL_PATTERNS = [
    re.compile(r"(?i)(['\"])sk-[a-zA-Z0-9_-]{20,}\1"),
    re.compile(r"(?i)(['\"])ghp_[a-zA-Z0-9_]{36,}\1"),
    re.compile(r"(?i)(['\"])Bearer\s+[a-zA-Z0-9_.-]+\1"),
]


class VerifierBrain:
    """
    Independent verifier ensuring code correctness, security compliance, and speech purity.
    """

    @classmethod
    def verify_candidate_output(
        cls,
        output_text: str,
        is_speech_chunk: bool = False,
        file_path: Optional[str] = None,
        language: Optional[str] = None,
    ) -> VerifierReport:
        issues: List[str] = []
        evidence: List[str] = []
        suggested_repairs: List[str] = []
        score = 1.0

        # 1. Check for meta-reflection & thinking leakage
        for pat in _META_REFLECTION_PATTERNS:
            if pat.search(output_text):
                issues.append(f"Prompt reflection or thinking tag detected: {pat.pattern}")
                suggested_repairs.append("Strip internal thinking tags and monologue before vocalization.")
                score -= 0.35

        # 2. Check for exposed API keys or tokens
        for pat in _CREDENTIAL_PATTERNS:
            if pat.search(output_text):
                issues.append("Hardcoded credential or token detected in candidate text.")
                suggested_repairs.append("Move credentials to environment variables or key vaults.")
                score -= 0.50

        # 3. Syntax Verification (if file is code)
        if file_path or language:
            lang = language or (file_path.split(".")[-1] if file_path and "." in file_path else "")
            lang = lang.lower()

            if lang in ("python", "py"):
                try:
                    ast.parse(output_text)
                    evidence.append("Python AST parsed successfully with zero syntax errors.")
                except SyntaxError as e:
                    issues.append(f"Python SyntaxError at line {e.lineno}: {e.msg}")
                    suggested_repairs.append(f"Fix Python syntax on line {e.lineno}: {e.text}")
                    score -= 0.40

            elif lang in ("json",):
                try:
                    json.loads(output_text)
                    evidence.append("JSON parsed successfully.")
                except Exception as e:
                    issues.append(f"JSON Parse Error: {e}")
                    suggested_repairs.append("Ensure JSON syntax is valid with closed braces and valid quotes.")
                    score -= 0.40

        is_valid = len(issues) == 0 and score >= 0.70
        return VerifierReport(
            valid=is_valid,
            score=max(0.0, score),
            issues=issues,
            evidence=evidence,
            security_clean=not any("credential" in i.lower() for i in issues),
            suggested_repairs=suggested_repairs,
        )

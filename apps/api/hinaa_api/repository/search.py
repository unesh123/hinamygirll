"""B3 Multi-Modal Repository Search & Neighborhood Retrieval (Directives §4–§7).

Implements:
1. Multi-factor symbol search (lexical, token overlap, exact name).
2. Graph neighborhood expansion (1-hop/2-hop callers, callees, tests).
3. Code snippet extraction around target lines.
4. Structured summary ready for ContextCompiler injection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import os
import re
from typing import Any

from .models import RepositoryMap, Symbol, SymbolGraph


@dataclass
class RepositorySearchResult:
    symbol: Symbol
    snippet: str
    relevance_score: float
    callers: list[Symbol] = field(default_factory=list)
    callees: list[Symbol] = field(default_factory=list)
    tests: list[Symbol] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol.to_dict(),
            "snippet": self.snippet,
            "relevance_score": round(self.relevance_score, 3),
            "callers": [c.to_dict() for c in self.callers],
            "callees": [c.to_dict() for c in self.callees],
            "tests": [t.to_dict() for t in self.tests],
        }


class RepositorySearchEngine:
    def __init__(self, repo_map: RepositoryMap) -> None:
        self.repo_map = repo_map
        self.graph = repo_map.graph

    def search(self, query: str, limit: int = 5) -> list[RepositorySearchResult]:
        """Search repository for symbols and their graph neighborhoods."""
        q = query.strip().lower()
        if not q:
            return []

        q_terms = set(re.findall(r"\w+", q))
        scored: list[tuple[float, Symbol]] = []

        for sym in self.graph.symbols.values():
            score = 0.0
            s_name = sym.name.lower()
            s_path = sym.file_path.lower()
            s_doc = sym.docstring.lower()

            # Exact match
            if q == s_name or q == sym.name:
                score += 10.0
            # Substring match in symbol name
            elif q in s_name:
                score += 5.0
            else:
                # Word overlap in name, path, and docstring
                name_words = set(re.findall(r"\w+", s_name))
                path_words = set(re.findall(r"\w+", s_path))
                doc_words = set(re.findall(r"\w+", s_doc))

                overlap_name = len(q_terms & name_words)
                overlap_path = len(q_terms & path_words)
                overlap_doc = len(q_terms & doc_words)

                score += overlap_name * 3.0 + overlap_path * 1.5 + overlap_doc * 0.5

            if score > 0.0:
                scored.append((score, sym))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        top_syms = scored[:limit]

        results: list[RepositorySearchResult] = []
        for score, sym in top_syms:
            neighborhood = self.graph.get_neighborhood(sym.symbol_id)
            snippet = self._extract_snippet(sym)
            results.append(
                RepositorySearchResult(
                    symbol=sym,
                    snippet=snippet,
                    relevance_score=score,
                    callers=neighborhood.get("callers", []),
                    callees=neighborhood.get("callees", []),
                    tests=neighborhood.get("tests", []),
                )
            )

        return results

    def _extract_snippet(self, sym: Symbol, context_lines: int = 8) -> str:
        full_path = os.path.join(self.repo_map.root_path, sym.file_path)
        if not os.path.exists(full_path):
            return ""

        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            start_idx = max(0, sym.line_start - 1 - context_lines)
            end_idx = min(len(lines), sym.line_end + context_lines)

            snippet_lines = lines[start_idx:end_idx]
            return "".join(snippet_lines)
        except Exception:
            return ""

    def format_search_context(self, query: str, results: list[RepositorySearchResult]) -> str:
        """Format search hits for ContextCompiler injection."""
        if not results:
            return f"Repository search for '{query}': No matching symbols found."

        blocks = [f"REPOSITORY NEIGHBORHOOD SEARCH for '{query}' ({len(results)} matches):"]
        for idx, res in enumerate(results, 1):
            s = res.symbol
            callers_str = ", ".join(c.name for c in res.callers) or "none"
            callees_str = ", ".join(c.name for c in res.callees) or "none"
            tests_str = ", ".join(t.name for t in res.tests) or "none"

            blocks.append(
                f"\n[{idx}] {s.kind.value.upper()} `{s.name}` in `{s.file_path}:{s.line_start}-{s.line_end}` (Score: {res.relevance_score}):\n"
                f"  Callers: {callers_str}\n"
                f"  Callees: {callees_str}\n"
                f"  Tests: {tests_str}\n"
                f"  Code Context:\n```\n{res.snippet.strip()}\n```"
            )
        return "\n".join(blocks)

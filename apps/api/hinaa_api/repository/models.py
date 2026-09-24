"""B3 Repository Map & Git Workspace Domain Models (Directives §1–§8).

Defines:
1. Symbol and SymbolKind (function, class, method, route, hook, component, model).
2. SymbolRelation and RelationType (calls, imports, implements, tests, references).
3. SymbolGraph with multi-hop neighborhood retrieval.
4. RepositoryMap compact hierarchical tree generator.
5. GitHubPermission hierarchy and GitWorkspace state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import os
from typing import Any


class SymbolKind(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    ROUTE = "route"
    HOOK = "hook"
    COMPONENT = "component"
    MODEL = "model"
    INTERFACE = "interface"
    VARIABLE = "variable"


class RelationType(str, Enum):
    CALLS = "calls"
    IMPORTS = "imports"
    IMPLEMENTS = "implements"
    TESTS = "tests"
    REFERENCES = "references"
    DEFINES = "defines"


@dataclass
class Symbol:
    name: str
    kind: SymbolKind
    file_path: str
    line_start: int
    line_end: int
    signature: str = ""
    docstring: str = ""
    is_exported: bool = True
    symbol_id: str = ""

    def __post_init__(self) -> None:
        if not self.symbol_id:
            norm_path = self.file_path.replace("\\", "/")
            self.symbol_id = f"{norm_path}:{self.name}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol_id": self.symbol_id,
            "name": self.name,
            "kind": self.kind.value,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "signature": self.signature,
            "docstring": self.docstring,
            "is_exported": self.is_exported,
        }


@dataclass(frozen=True)
class SymbolRelation:
    source_id: str
    target_id: str
    relation_type: RelationType
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SymbolGraph:
    symbols: dict[str, Symbol] = field(default_factory=dict)
    edges: list[SymbolRelation] = field(default_factory=list)
    _outgoing: dict[str, list[SymbolRelation]] = field(default_factory=dict)
    _incoming: dict[str, list[SymbolRelation]] = field(default_factory=dict)

    def add_symbol(self, symbol: Symbol) -> None:
        self.symbols[symbol.symbol_id] = symbol

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        rel = SymbolRelation(
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
            metadata=metadata or {},
        )
        self.edges.append(rel)
        self._outgoing.setdefault(source_id, []).append(rel)
        self._incoming.setdefault(target_id, []).append(rel)

    def get_symbol(self, symbol_id: str) -> Symbol | None:
        return self.symbols.get(symbol_id)

    def find_symbols(self, name_query: str, exact: bool = False) -> list[Symbol]:
        query = name_query.lower()
        exact_matches: list[Symbol] = []
        partial_matches: list[Symbol] = []
        for sym in self.symbols.values():
            if query == sym.name.lower():
                exact_matches.append(sym)
            elif not exact and query in sym.name.lower():
                partial_matches.append(sym)
        if exact:
            return exact_matches
        return exact_matches + partial_matches

    def get_neighborhood(self, symbol_id: str, depth: int = 1) -> dict[str, Any]:
        """Neighborhood search (P0.15 / B3 §4): returns target node, callers, callees, and tests."""
        center = self.symbols.get(symbol_id)
        if not center:
            return {"center": None, "callers": [], "callees": [], "tests": [], "imports": []}

        outgoing_rels = self._outgoing.get(symbol_id, [])
        incoming_rels = self._incoming.get(symbol_id, [])

        callees: list[Symbol] = []
        callers: list[Symbol] = []
        tests: list[Symbol] = []
        imports: list[Symbol] = []

        for rel in outgoing_rels:
            target = self.symbols.get(rel.target_id)
            if target:
                if rel.relation_type == RelationType.CALLS:
                    callees.append(target)
                elif rel.relation_type == RelationType.IMPORTS:
                    imports.append(target)

        for rel in incoming_rels:
            source = self.symbols.get(rel.source_id)
            if source:
                if rel.relation_type == RelationType.CALLS:
                    callers.append(source)
                elif rel.relation_type == RelationType.TESTS:
                    tests.append(source)

        return {
            "center": center,
            "callers": callers,
            "callees": callees,
            "tests": tests,
            "imports": imports,
        }


@dataclass
class RepositoryMap:
    root_path: str
    graph: SymbolGraph
    file_count: int = 0
    language_counts: dict[str, int] = field(default_factory=dict)
    file_symbols: dict[str, list[Symbol]] = field(default_factory=dict)
    token_estimate: int = 0

    def to_compact_tree(self, max_tokens: int = 2000) -> str:
        """Render a compact AST-anchored tree representation for LLM context injection."""
        lines: list[str] = [f"REPOSITORY MAP ({self.file_count} files, root: {os.path.basename(self.root_path)}):"]
        
        # Group by directory/file
        sorted_files = sorted(self.file_symbols.keys())
        for fpath in sorted_files:
            syms = self.file_symbols[fpath]
            lines.append(f"  {fpath}:")
            # Highlight routes, classes, exports
            for s in syms:
                kind_str = s.kind.value
                sig_str = f"({s.signature})" if s.signature else ""
                lines.append(f"    - [{kind_str}] {s.name}{sig_str} (L{s.line_start}-{s.line_end})")

        rendered = "\n".join(lines)
        return rendered


class GitHubPermission(str, Enum):
    READ_ONLY = "read_only"
    WORKSPACE_WRITE = "workspace_write"
    COMMIT = "commit"
    PUSH_BRANCH = "push_branch"
    CREATE_PR = "create_pr"
    MERGE_PR = "merge_pr"


_PERMISSION_RANKS: dict[GitHubPermission, int] = {
    GitHubPermission.READ_ONLY: 1,
    GitHubPermission.WORKSPACE_WRITE: 2,
    GitHubPermission.COMMIT: 3,
    GitHubPermission.PUSH_BRANCH: 4,
    GitHubPermission.CREATE_PR: 5,
    GitHubPermission.MERGE_PR: 6,
}


def check_github_permission(granted: GitHubPermission, required: GitHubPermission) -> bool:
    """Verifies that the granted permission level meets or exceeds the required level."""
    return _PERMISSION_RANKS.get(granted, 0) >= _PERMISSION_RANKS.get(required, 0)


@dataclass
class DirtyFile:
    path: str
    status: str  # 'M', 'A', 'D', '??'
    is_staged: bool = False


@dataclass
class GitWorkspace:
    root_path: str
    branch: str
    head_commit: str
    dirty_files: list[DirtyFile] = field(default_factory=list)
    permission: GitHubPermission = GitHubPermission.WORKSPACE_WRITE

    @property
    def is_dirty(self) -> bool:
        return len(self.dirty_files) > 0

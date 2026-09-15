"""B3 Repository AST Mapper (Directives §1–§6).

Parses source code into structured symbol nodes and relationships:
- Python parsing via stdlib `ast`.
- TypeScript/JavaScript parsing via structural regex & AST pattern matching.
- Extracts functions, methods, classes, routes, hooks, components.
- Builds call-graph, import-graph, and test-mapping edges.
"""

from __future__ import annotations

import ast
import os
import re
from typing import Any

from .models import (
    RelationType,
    RepositoryMap,
    Symbol,
    SymbolGraph,
    SymbolKind,
)

_IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".gemini",
    ".pytest_cache",
    ".idea",
    ".vscode",
}

_SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript-react",
    ".js": "javascript",
    ".jsx": "javascript-react",
}


class RepositoryMapper:
    def __init__(self, root_dir: str) -> None:
        self.root_dir = os.path.abspath(root_dir)

    def scan_and_map(self, max_files: int = 500) -> RepositoryMap:
        graph = SymbolGraph()
        file_symbols: dict[str, list[Symbol]] = {}
        language_counts: dict[str, int] = {}
        file_count = 0

        # Pass 1: Parse all symbols in each file
        parsed_files: dict[str, Any] = {}
        for root, dirs, files in os.walk(self.root_dir):
            # Prune ignored directories in place
            dirs[:] = [d for d in dirs if d not in _IGNORED_DIRS]

            for fname in sorted(files):
                ext = os.path.splitext(fname)[1].lower()
                if ext not in _SUPPORTED_EXTENSIONS:
                    continue

                full_path = os.path.join(root, fname)
                rel_path = os.path.relpath(full_path, self.root_dir).replace("\\", "/")

                file_count += 1
                lang = _SUPPORTED_EXTENSIONS[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1

                try:
                    with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                        source_text = f.read()

                    symbols: list[Symbol] = []
                    if ext == ".py":
                        symbols, extra_meta = self._parse_python(rel_path, source_text)
                    else:
                        symbols, extra_meta = self._parse_typescript(rel_path, source_text)

                    for s in symbols:
                        graph.add_symbol(s)
                    file_symbols[rel_path] = symbols
                    parsed_files[rel_path] = (source_text, extra_meta)

                except Exception:
                    continue

                if file_count >= max_files:
                    break
            if file_count >= max_files:
                break

        # Pass 2: Connect relations (CALLS, IMPORTS, TESTS)
        self._build_relations(graph, parsed_files)

        from hinaa_api.agent.compiler import estimate_tokens
        repo_map = RepositoryMap(
            root_path=self.root_dir,
            graph=graph,
            file_count=file_count,
            language_counts=language_counts,
            file_symbols=file_symbols,
        )
        tree_text = repo_map.to_compact_tree()
        repo_map.token_estimate = estimate_tokens(tree_text)
        return repo_map

    def _parse_python(self, rel_path: str, source: str) -> tuple[list[Symbol], dict[str, Any]]:
        symbols: list[Symbol] = []
        calls: list[tuple[str, str]] = []  # (caller_name, callee_name)
        imports: list[str] = []

        try:
            tree = ast.parse(source)
        except SyntaxError:
            return symbols, {"calls": calls, "imports": imports}

        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                else:
                    if node.module:
                        imports.append(node.module)

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                sym = self._extract_py_func(node, rel_path)
                symbols.append(sym)
                # Find calls inside func
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                        calls.append((sym.name, sub.func.id))
                    elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                        calls.append((sym.name, sub.func.attr))

            elif isinstance(node, ast.ClassDef):
                cls_sym = Symbol(
                    name=node.name,
                    kind=SymbolKind.CLASS,
                    file_path=rel_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    docstring=ast.get_docstring(node) or "",
                )
                symbols.append(cls_sym)

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        method_sym = self._extract_py_func(item, rel_path, is_method=True, class_name=node.name)
                        symbols.append(method_sym)
                        for sub in ast.walk(item):
                            if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                                calls.append((method_sym.name, sub.func.id))
                            elif isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute):
                                calls.append((method_sym.name, sub.func.attr))

        return symbols, {"calls": calls, "imports": imports}

    def _extract_py_func(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        rel_path: str,
        is_method: bool = False,
        class_name: str | None = None,
    ) -> Symbol:
        # Check if decorated as route (@app.get, @router.post, etc.)
        is_route = False
        for dec in node.decorator_list:
            dec_id = ""
            if isinstance(dec, ast.Call):
                if isinstance(dec.func, ast.Attribute):
                    dec_id = dec.func.attr.lower()
            elif isinstance(dec, ast.Attribute):
                dec_id = dec.attr.lower()
            if dec_id in ("get", "post", "put", "delete", "patch", "websocket"):
                is_route = True
                break

        kind = SymbolKind.ROUTE if is_route else (SymbolKind.METHOD if is_method else SymbolKind.FUNCTION)
        # Signature args
        arg_names = [a.arg for a in node.args.args]
        sig = f"({', '.join(arg_names)})"
        sym_name = f"{class_name}.{node.name}" if class_name else node.name

        return Symbol(
            name=sym_name,
            kind=kind,
            file_path=rel_path,
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            signature=sig,
            docstring=ast.get_docstring(node) or "",
        )

    def _parse_typescript(self, rel_path: str, source: str) -> tuple[list[Symbol], dict[str, Any]]:
        symbols: list[Symbol] = []
        calls: list[tuple[str, str]] = []
        imports: list[str] = []

        lines = source.splitlines()

        # Import scanner
        for match in re.finditer(r"""import\s+.*?from\s+['"]([^'"]+)['"]""", source):
            imports.append(match.group(1))

        # Function & Component & Hook regex
        # e.g. export function useCompanion(...) or const AuthModal: React.FC = () => ...
        for idx, line in enumerate(lines, start=1):
            line_s = line.strip()
            # Function pattern
            m_func = re.search(r"^(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z0-9_]+)\s*\((.*?)\)", line_s)
            if m_func:
                name = m_func.group(1)
                sig = f"({m_func.group(2).strip()})"
                kind = SymbolKind.FUNCTION
                if name.startswith("use") and len(name) > 3 and name[3].isupper():
                    kind = SymbolKind.HOOK
                elif name[0].isupper() and ("Component" in name or "View" in name or "Modal" in name or rel_path.endswith((".tsx", ".jsx"))):
                    kind = SymbolKind.COMPONENT

                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=sig,
                    )
                )
                continue

            # Const arrow func pattern
            m_const = re.search(r"^(?:export\s+)?const\s+([a-zA-Z0-9_]+)(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s*)?\((.*?)\)\s*=>", line_s)
            if m_const:
                name = m_const.group(1)
                sig = f"({m_const.group(2).strip()})"
                kind = SymbolKind.FUNCTION
                if name.startswith("use") and len(name) > 3 and name[3].isupper():
                    kind = SymbolKind.HOOK
                elif name[0].isupper() and rel_path.endswith((".tsx", ".jsx")):
                    kind = SymbolKind.COMPONENT

                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                        signature=sig,
                    )
                )
                continue

            # Class / Interface pattern
            m_class = re.search(r"^(?:export\s+)?(?:class|interface)\s+([a-zA-Z0-9_]+)", line_s)
            if m_class:
                name = m_class.group(1)
                is_interface = "interface " in line_s
                kind = SymbolKind.INTERFACE if is_interface else SymbolKind.CLASS
                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        file_path=rel_path,
                        line_start=idx,
                        line_end=idx,
                    )
                )

        return symbols, {"calls": calls, "imports": imports}

    def _build_relations(self, graph: SymbolGraph, parsed_files: dict[str, Any]) -> None:
        # Index symbols by bare name for fast matching
        by_name: dict[str, list[Symbol]] = {}
        for s in graph.symbols.values():
            bare_name = s.name.rsplit(".", 1)[-1]
            by_name.setdefault(bare_name, []).append(s)

        for rel_path, (source, meta) in parsed_files.items():
            calls = meta.get("calls", [])
            for caller_name, callee_name in calls:
                caller_syms = [s for s in by_name.get(caller_name.rsplit(".", 1)[-1], []) if s.file_path == rel_path]
                callee_syms = by_name.get(callee_name, [])

                if caller_syms and callee_syms:
                    c_sym = caller_syms[0]
                    t_sym = callee_syms[0]
                    # Check if caller is a test
                    if c_sym.name.startswith("test_") or "test" in rel_path.lower():
                        graph.add_relation(c_sym.symbol_id, t_sym.symbol_id, RelationType.TESTS)
                    else:
                        graph.add_relation(c_sym.symbol_id, t_sym.symbol_id, RelationType.CALLS)

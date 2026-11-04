"""Read source/manifests without importing app modules or inspecting secrets.

Writes a reproducible structural inventory, not a security certification or
claim that a declared dependency/integration is installed or operational.
"""
from __future__ import annotations
import argparse
import ast
from collections import Counter
import importlib.metadata
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def inventory() -> dict:
    backend = sorted((ROOT / "apps/api/hinaa_api").rglob("*.py"))
    frontend = sorted(p for p in (ROOT / "apps/web/src").rglob("*") if p.suffix in {".ts", ".tsx"})
    providers, routes, errors = [], [], []
    for path in backend:
        relative = path.relative_to(ROOT).as_posix()
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=relative)
        except (SyntaxError, UnicodeError) as error:
            errors.append({"path": relative, "error": type(error).__name__, "line": getattr(error, "lineno", None)})
            continue
        if path.parent.name == "providers":
            providers.extend({"path": relative, "class": node.name, "line": node.lineno}
                             for node in tree.body if isinstance(node, ast.ClassDef))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                    continue
                if decorator.func.attr not in {"get", "post", "put", "patch", "delete", "websocket"}:
                    continue
                if decorator.args and isinstance(decorator.args[0], ast.Constant) and isinstance(decorator.args[0].value, str):
                    routes.append({"method": decorator.func.attr.upper(), "route": decorator.args[0].value,
                                   "handler": node.name, "path": relative, "line": node.lineno})
    requirements = []
    for line in (ROOT / "apps/api/requirements.txt").read_text().splitlines():
        if not line.strip() or line.lstrip().startswith(("#", "-")):
            continue
        name = re.split(r"[<>=!~\[]", line, maxsplit=1)[0].strip()
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        requirements.append({"declared": line, "installedInAuditInterpreter": installed})
    web = json.loads((ROOT / "apps/web/package.json").read_text())
    modes = ast.parse((ROOT / "apps/api/hinaa_api/models.py").read_text())
    mode_names = []
    for statement in modes.body:
        if isinstance(statement, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "ProviderMode" for t in statement.targets):
            mode_names = [n.value for n in ast.walk(statement.value) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    return {
        "scope": "Structural inventory of active source and manifests; excludes vendor archives, installed packages, secrets and user data",
        "counts": {"backendPythonFiles": len(backend), "frontendSourceFiles": len(frontend),
                   "backendTestFiles": len(list((ROOT / "apps/api/tests").rglob("test_*.py"))),
                   "frontendTestFiles": sum(bool(re.search(r"\.(test|spec)\.tsx?$", p.name)) for p in frontend),
                   "routeDeclarationsIncludingAliases": len(routes)},
        "backendAreas": dict(sorted(Counter(p.relative_to(ROOT / "apps/api/hinaa_api").parts[0] if p.parent != ROOT / "apps/api/hinaa_api" else "root" for p in backend).items())),
        "parseErrors": errors, "providerModes": mode_names, "providerClasses": providers,
        "routes": routes, "backendRequirements": requirements,
        "frontendDependencies": web.get("dependencies", {}), "frontendDevDependencies": web.get("devDependencies", {}),
        "recommendedButNotDeclaredHere": ["langgraph", "redis", "transformers", "peft"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/repository-audit-2026-11-04.json")
    args = parser.parse_args()
    report = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "parseErrors": report["parseErrors"],
                      "providerModes": report["providerModes"],
                      "missingDeclaredBackendDependencies": [r["declared"] for r in report["backendRequirements"] if r["installedInAuditInterpreter"] is None]}, indent=2))

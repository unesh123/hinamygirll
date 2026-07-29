"""Validate HINAA Phase 0 documentation and interface artifacts without network access."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md", ".env.example", "openapi/hinaa-api.yaml",
    *[f"docs/{i:02d}-{name}.md" for i, name in enumerate([
        "executive-summary", "product-vision", "scope-and-requirements",
        "user-stories-and-use-cases", "system-architecture", "realtime-event-protocol",
        "avatar-emotion-and-motion-engine", "nepali-voice-evaluation", "ai-provider-routing",
        "memory-and-database", "security-privacy-threat-model", "prompt-and-personality-architecture",
        "mobile-ux-and-design-system", "error-handling", "testing-and-observability",
        "deployment-and-devops", "cost-and-subscription-plan", "roadmap",
        "final-year-report-map", "risk-register", "open-questions", "assumptions",
        "requirements-traceability-matrix"
    ])],
    "docs/ASSET_LICENSES.md", "docs/GLOSSARY.md", "docs/DEPENDENCY_BASELINE.md", "docs/adr/README.md",
    "packages/contracts/schemas/assistant-turn-plan.schema.json",
    "packages/contracts/schemas/realtime-event.schema.json",
]

EVENTS = {
    "session.started", "microphone.started", "microphone.stopped", "user.audio.chunk",
    "user.transcript.partial", "user.transcript.final", "assistant.turn.started",
    "assistant.text.delta", "assistant.text.completed", "assistant.emotion.changed",
    "assistant.motion.cue", "assistant.viseme.frame", "assistant.audio.chunk",
    "assistant.audio.completed", "assistant.interrupted", "provider.fallback",
    "tool.approval.required", "error", "session.completed",
}


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def validate_json(errors: list[str]) -> None:
    schemas = {}
    for path in (ROOT / "packages/contracts/schemas").glob("*.json"):
        try:
            schemas[path.name] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"Invalid JSON {path.relative_to(ROOT)}: {exc}", errors)
    event_enum = set(schemas.get("realtime-event.schema.json", {}).get("properties", {}).get("type", {}).get("enum", []))
    if event_enum != EVENTS:
        fail(f"Realtime event enum mismatch: missing={EVENTS-event_enum}, extra={event_enum-EVENTS}", errors)

    try:
        import jsonschema  # type: ignore
        for name, schema in schemas.items():
            try:
                jsonschema.Draft202012Validator.check_schema(schema)
            except Exception as exc:
                fail(f"Invalid JSON Schema {name}: {exc}", errors)
    except ImportError:
        jsonschema = None

    examples = list((ROOT / "packages/contracts/examples").glob("*.json"))
    for path in examples:
        try:
            instance = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            fail(f"Invalid example JSON {path.relative_to(ROOT)}: {exc}", errors)
            continue
        if jsonschema is None:
            continue
        schema_name = "assistant-turn-plan.schema.json" if "spokenText" in instance else "realtime-event.schema.json"
        try:
            jsonschema.Draft202012Validator(schemas[schema_name], format_checker=jsonschema.FormatChecker()).validate(instance)
        except Exception as exc:
            fail(f"Schema failure {path.relative_to(ROOT)}: {exc}", errors)


def validate_yaml(errors: list[str]) -> None:
    path = ROOT / "openapi/hinaa-api.yaml"
    try:
        import yaml  # type: ignore
    except ImportError:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("openapi: 3.1.0") or "\npaths:" not in text or "\ncomponents:" not in text:
            fail("OpenAPI structural markers missing (PyYAML unavailable)", errors)
        return
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
        if doc.get("openapi") != "3.1.0" or not doc.get("paths") or not doc.get("components"):
            fail("OpenAPI document is missing required root sections", errors)
            return
        operation_ids: list[str] = []

        def walk(value: object) -> None:
            if isinstance(value, dict):
                ref = value.get("$ref")
                if isinstance(ref, str) and ref.startswith("#/"):
                    cursor: object = doc
                    try:
                        for token in ref[2:].split("/"):
                            cursor = cursor[token.replace("~1", "/").replace("~0", "~")]  # type: ignore[index]
                    except Exception:
                        fail(f"Unresolved OpenAPI reference: {ref}", errors)
                op = value.get("operationId")
                if isinstance(op, str):
                    operation_ids.append(op)
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(doc)
        duplicates = {op for op in operation_ids if operation_ids.count(op) > 1}
        if duplicates:
            fail(f"Duplicate OpenAPI operationId values: {sorted(duplicates)}", errors)
    except Exception as exc:
        fail(f"Invalid OpenAPI YAML: {exc}", errors)


def validate_links(errors: list[str]) -> None:
    pattern = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
    for path in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md"), *(ROOT / "packages").rglob("*.md")]:
        text = path.read_text(encoding="utf-8")
        for target in pattern.findall(text):
            target = target.split("#", 1)[0].strip("<>")
            if not target or re.match(r"^(https?://|mailto:)", target):
                continue
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                fail(f"Broken local link in {path.relative_to(ROOT)}: {target}", errors)


def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        if not (ROOT / rel).is_file():
            fail(f"Missing required file: {rel}", errors)
    diagrams = list((ROOT / "docs/diagrams").glob("*.mmd"))
    if len(diagrams) != 5:
        fail(f"Expected 5 Mermaid sources, found {len(diagrams)}", errors)
    validate_json(errors)
    validate_yaml(errors)
    validate_links(errors)
    if errors:
        print("Blueprint validation FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Blueprint validation PASSED")
    print(f"Required files: {len(REQUIRED)}; Mermaid diagrams: {len(diagrams)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

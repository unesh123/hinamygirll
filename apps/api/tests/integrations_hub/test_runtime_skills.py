from __future__ import annotations

from pathlib import Path

from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.assembly import assemble_prompt
from hinaa_api.skills import loader as skill_loader
from hinaa_api.skills.loader import SkillLoader, parse_skill, skill_block_for_turn


def _write(root: Path, name: str, description: str, body: str, *, folded: bool = False) -> None:
    d = root / name
    d.mkdir(parents=True)
    desc = f">-\n  {description}" if folded else description
    (d / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {desc}\n---\n{body}\n", encoding="utf-8")


def _loader(tmp_path: Path) -> SkillLoader:
    root = tmp_path / "skills"
    _write(root, "postgres-tuning", "Tune postgres indexes and slow queries", "USE EXPLAIN ANALYZE first.", folded=True)
    _write(root, "watercolor-painting", "Paint watercolor landscapes with washes", "Wet on wet technique.")
    _write(root, "kubernetes-debug", "Debug kubernetes pod crashloops and deployments", "kubectl describe pod.")
    return SkillLoader([root])


def test_parse_skill_handles_folded_description():
    skill = parse_skill("---\nname: x\ndescription: >-\n  line one\n  line two\n---\nBody here", "fallback")
    assert (skill.name, skill.description, skill.body) == ("x", "line one line two", "Body here")
    assert parse_skill("no frontmatter body", "dir").name == "dir"


def test_select_is_deterministic_and_relevant(tmp_path):
    loader = _loader(tmp_path)
    picks = [s.name for s in loader.select("my postgres queries are slow, tune the indexes")]
    assert picks == ["postgres-tuning"]
    assert picks == [s.name for s in loader.select("my postgres queries are slow, tune the indexes")]
    assert loader.select("hello how are you today") == []


def test_block_truncates_and_can_be_disabled(tmp_path, monkeypatch):
    root = tmp_path / "skills"
    _write(root, "postgres-tuning", "Tune postgres indexes and slow queries", "x" * 20_000)
    for i, topic in enumerate(("painting", "baking", "sailing", "poetry")):
        _write(root, f"filler-{i}", f"Notes about {topic}", "filler")
    loader = SkillLoader([root])
    block = skill_block_for_turn("tune postgres indexes", loader=loader)
    assert block.startswith("RELEVANT SKILL PLAYBOOKS") and len(block) <= skill_loader.MAX_BLOCK_CHARS
    monkeypatch.setenv("HINAA_RUNTIME_SKILLS_ENABLED", "false")
    assert skill_block_for_turn("tune postgres indexes", loader=loader) == ""


def test_cache_reloads_when_files_change(tmp_path):
    loader = _loader(tmp_path)
    first = loader.load()
    assert loader.load() is first
    _write(tmp_path / "skills", "redis-caching", "Configure redis cache eviction", "maxmemory-policy")
    assert "redis-caching" in {s.name for s in loader.load()}


def test_repo_skills_load_from_project_root():
    names = {s.name for s in SkillLoader().load()}
    assert "clerk-cli" in names


def test_prompt_injection_layer():
    base = dict(companion_id="hinaa", interaction_mode="rest", user_text="tune postgres")
    plain = assemble_prompt(PromptInput(**base))
    assert "skill_playbooks" not in plain.user_contents
    injected = assemble_prompt(PromptInput(**base, runtime_skill_block="RELEVANT SKILL PLAYBOOKS\nUSE EXPLAIN"))
    assert "USE EXPLAIN" in injected.user_contents
    layer = next(layer for layer in injected.layers if layer.name == "runtime_skills")
    assert layer.trusted is False
    assert injected.fingerprint != plain.fingerprint

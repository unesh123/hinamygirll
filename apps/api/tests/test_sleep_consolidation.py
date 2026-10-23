"""
Tests for HINAA Stateful Sleep-Cycle Memory Consolidation Engine.
"""

import json
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hinaa_api.intelligence.sleep_consolidation import (
    SleepCycleConsolidator,
    memory_consolidate_cycle_handler,
)


def test_triple_extraction_from_text():
    consolidator = SleepCycleConsolidator()

    text_pref = "I prefer dark mode everywhere and I like TypeScript."
    triples = consolidator.extract_triples_from_text(text_pref, user_name="LORD")
    assert len(triples) >= 2
    assert any(t[1] == "prefers" and "dark mode" in t[2] for t in triples)
    assert any(t[1] == "prefers" and "typescript" in t[2].lower() for t in triples)

    text_stack = "Project architecture written in Python with FastAPI."
    triples_stack = consolidator.extract_triples_from_text(text_stack)
    assert any(t[0] == "Project" and "fastapi" in t[2].lower() for t in triples_stack)


def test_contradiction_resolution_and_supersession(tmp_path):
    consolidator = SleepCycleConsolidator(memory_dir=tmp_path)
    now = time.time()

    # Step 1: Learn first fact: dark mode
    res1 = consolidator.run_consolidation_cycle(
        user_id="LORD",
        source_texts=["I prefer dark mode."],
        dry_run=False,
    )
    assert res1["success"] is True
    assert res1["total_active_facts"] == 1
    dark_key = consolidator._make_key("LORD", "prefers", "dark mode")
    assert dark_key in consolidator.facts
    assert consolidator.facts[dark_key].status == "active"

    # Step 2: Learn contradictory fact: light mode
    res2 = consolidator.run_consolidation_cycle(
        user_id="LORD",
        source_texts=["Actually, I prefer light mode now."],
        dry_run=False,
    )
    assert res2["success"] is True
    # The dark mode fact must now be marked superseded!
    assert consolidator.facts[dark_key].status == "superseded"
    assert "light mode" in (consolidator.facts[dark_key].superseded_by or "").lower()

    # The light mode fact must be active!
    light_key = consolidator._make_key("LORD", "prefers", "light mode")
    assert light_key in consolidator.facts
    assert consolidator.facts[light_key].status == "active"


def test_decay_and_pruning(tmp_path):
    consolidator = SleepCycleConsolidator(decay_half_life_days=7.0, memory_dir=tmp_path)
    now = time.time()

    # Create an old low-importance fact from 30 days ago
    key = "user:prefers:stale_temp"
    from hinaa_api.intelligence.sleep_consolidation import ConsolidatedFact
    consolidator.facts[key] = ConsolidatedFact(
        subject="user",
        predicate="prefers",
        target="stale_temp",
        confidence=0.5,
        importance=1.0,  # low importance decays fast
        created_at=now - (30 * 86400),
        last_reinforced=now - (30 * 86400),
        status="active",
    )

    decayed, pruned = consolidator.apply_decay_and_prune(now)
    assert decayed >= 1
    assert consolidator.facts[key].status == "decayed"


def test_disk_persistence_and_reload(tmp_path):
    consolidator1 = SleepCycleConsolidator(memory_dir=tmp_path)
    consolidator1.run_consolidation_cycle(
        user_id="LORD",
        source_texts=["I prefer Neovim over VS Code."],
        dry_run=False,
    )

    graph_file = tmp_path / "knowledge-graph.json"
    assert graph_file.exists()

    with open(graph_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["version"] == "2026.1"
    assert data["active_facts_count"] >= 1

    # Reload into fresh consolidator instance
    consolidator2 = SleepCycleConsolidator(memory_dir=tmp_path)
    assert len(consolidator2.facts) >= 1
    key = consolidator2._make_key("LORD", "prefers", "neovim over vs code")
    assert key in consolidator2.facts
    assert consolidator2.facts[key].status == "active"


@pytest.mark.asyncio
async def test_memory_consolidate_tool_handler():
    res = await memory_consolidate_cycle_handler(
        user_id="LORD",
        sample_texts=["We always use Pydantic for validation."],
        dry_run=True,
    )
    assert res["success"] is True
    assert res["dry_run"] is True
    assert len(res["extracted_triples"]) >= 1
    assert any("pydantic" in t["target"].lower() for t in res["extracted_triples"])

"""
Unit tests for HINAA Advanced Architecture:
- 4-Tier Hybrid Vector + Graph Memory Store
- Self-Critique & Reflection Loop
- Multi-Agent Orchestration Layer
"""

import pytest
from hinaa_api.persistence.advanced_memory import (
    AdvancedMemoryManager,
    EpisodicVectorStore,
    ProceduralMemory,
    SemanticKnowledgeGraph,
    WorkingMemory,
)
from hinaa_api.agent.self_critique import SelfCritiqueEngine
from hinaa_api.agents.orchestrator import (
    AgentOrchestrator,
    AgentRole,
    TaskDecomposer,
)


class TestWorkingMemory:
    def test_buffer_overflow_bounds(self):
        wm = WorkingMemory(max_turns=4)
        for i in range(10):
            wm.add_turn("user", f"Turn {i}")
        assert len(wm.turns) == 4
        assert wm.turns[-1].content == "Turn 9"

    def test_goal_setting(self):
        wm = WorkingMemory()
        wm.set_goal("Build the advanced memory store")
        assert wm.get_goal() == "Build the advanced memory store"
        wm.clear()
        assert wm.get_goal() is None
        assert len(wm.turns) == 0


class TestEpisodicVectorStore:
    def test_recall_ranking_by_similarity(self):
        store = EpisodicVectorStore()
        store.record_episode("u1", "c1", "We talked about training the 3D avatar", importance=2.0)
        store.record_episode("u1", "c1", "We generated a photorealistic anime portrait", importance=3.0)
        store.record_episode("u1", "c1", "Python backend server on port 8000", importance=1.0)

        # Query about image generation
        results = store.recall("u1", "show me that portrait image we made", top_k=1)
        assert len(results) > 0
        best_ep, score = results[0]
        assert "portrait" in best_ep.content or "anime" in best_ep.content
        assert score > 0.1

    def test_user_isolation(self):
        store = EpisodicVectorStore()
        store.record_episode("u1", "c1", "Secret project Alpha")
        store.record_episode("u2", "c2", "Secret project Beta")

        u1_res = store.recall("u1", "Secret project")
        assert all(ep.user_id == "u1" for ep, _ in u1_res)


class TestSemanticKnowledgeGraph:
    def test_fact_consolidation_and_query(self):
        graph = SemanticKnowledgeGraph()
        graph.add_fact("Unesh", "works_on", "Hinaa AI Companion", confidence=0.9)
        graph.add_fact("Unesh", "likes", "Saiyara song", confidence=0.95)

        facts = graph.query_subgraph("what does Unesh like to listen to?")
        assert any("Saiyara song" in f for f in facts)

    def test_auto_extraction_from_dialogue(self):
        graph = SemanticKnowledgeGraph()
        extracted = graph.consolidate_turn_text("I love listening to ambient lofi music", user_name="Unesh")
        assert len(extracted) > 0
        assert any("lofi" in f for f in extracted)


class TestProceduralMemory:
    def test_tool_recipe_lookup(self):
        pm = ProceduralMemory()
        recipe = pm.get_recipe("I want to generate an image of a cybernetic cat")
        assert recipe is not None
        assert recipe.tool_name == "image_generate"
        assert "aspect_ratio" in recipe.recommended_parameters

    def test_execution_learning(self):
        pm = ProceduralMemory()
        initial_usage = pm.recipes["image_generate"].usage_count
        pm.record_execution("image_generate", success=True, params={"style": "cyberpunk"})
        assert pm.recipes["image_generate"].usage_count == initial_usage + 1
        assert pm.recipes["image_generate"].recommended_parameters.get("style") == "cyberpunk"


class TestAdvancedMemoryManager:
    def test_turn_orchestration(self):
        mgr = AdvancedMemoryManager()
        res = mgr.process_turn(
            user_id="u_dev",
            conversation_id="conv_1",
            user_text="I am working on the new Hinaa neural memory system",
            assistant_text="That sounds amazing! I am right here to help you architect it.",
        )
        assert res["working_turns"] == 2
        assert res["episode_id"] is not None

        # Context assembly
        ctx = mgr.assemble_memory_context("u_dev", "tell me about my project")
        assert len(ctx["recalled_episodes"]) > 0 or len(ctx["graph_facts"]) > 0


class TestSelfCritiqueEngine:
    def test_clean_response_passes(self):
        engine = SelfCritiqueEngine()
        result = engine.evaluate(
            user_prompt="How are you doing today?",
            response_text="Hey there! I'm feeling wonderful and super excited to work with you on our project!",
        )
        assert result.passed
        assert result.persona_score >= 0.9

    def test_robotic_hedge_fails_and_repairs(self):
        engine = SelfCritiqueEngine()
        result = engine.evaluate(
            user_prompt="Can you feel happy?",
            response_text="As an AI, I cannot experience emotions, but I am programmed to assist you.",
        )
        assert not result.passed
        assert result.persona_score < 0.7
        assert result.repaired_text is not None
        assert "As an AI" not in result.repaired_text


class TestMultiAgentOrchestrator:
    def test_single_domain_routing(self):
        orchestrator = AgentOrchestrator()
        code_plan = orchestrator.plan_execution("Write a Python function to compute cosine similarity")
        assert not code_plan.is_complex
        assert code_plan.primary_role == AgentRole.CODER

        research_plan = orchestrator.plan_execution("Who is Ada Lovelace and what was her contribution?")
        assert not research_plan.is_complex
        assert research_plan.primary_role == AgentRole.RESEARCHER

    def test_complex_multi_domain_decomposition(self):
        orchestrator = AgentOrchestrator()
        # Coding + Research + Creative
        plan = orchestrator.plan_execution(
            "Research the latest quantum computing algorithms and write python code to simulate qubits with a nice story"
        )
        assert plan.is_complex
        assert len(plan.subtasks) >= 3
        roles = [t.role for t in plan.subtasks]
        assert AgentRole.RESEARCHER in roles
        assert AgentRole.CODER in roles
        assert AgentRole.CRITIC in roles

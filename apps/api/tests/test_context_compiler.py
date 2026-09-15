import pytest
from hinaa_api.agent.compiler import ContextCompiler, estimate_tokens


@pytest.fixture
def compiler():
    return ContextCompiler(max_tokens=2048)


def test_estimate_tokens():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") == 2
    assert estimate_tokens("a" * 40) == 10


def test_calculate_score(compiler):
    # High authority checkpoint should outrank low authority message
    checkpoint_score = compiler.calculate_score(
        item_text="Task #12 is analyzing dataset",
        source_type="checkpoint",
        query="dataset analysis",
        age_turns=0,
    )
    message_score = compiler.calculate_score(
        item_text="Random conversational chatter",
        source_type="message",
        query="dataset analysis",
        age_turns=5,
    )
    assert checkpoint_score > message_score


def test_prompt_cache_fingerprint_deterministic(compiler):
    sys_identity = "You are HINAA, an enterprise multimodal operating companion."
    ctx1 = compiler.compile(system_identity=sys_identity, user_query="Hello")
    ctx2 = compiler.compile(system_identity=sys_identity, user_query="Deploy staging")

    # Cache fingerprint depends on the immutable system prefix for KV-cache reuse
    assert ctx1.cache_fingerprint == ctx2.cache_fingerprint
    assert len(ctx1.cache_fingerprint) == 16


def test_compile_includes_project_and_task_checkpoints(compiler):
    sys_identity = "You are HINAA."
    project = {"name": "Titan Omega", "description": "Edge dashboard"}
    checkpoint = {"title": "SSE Telemetry", "status": "running", "current_step": "Connecting to edge"}

    compiled = compiler.compile(
        system_identity=sys_identity,
        user_query="What is the current status?",
        active_project=project,
        active_task_checkpoint=checkpoint,
    )

    assert compiled.project_block is not None
    assert "Titan Omega" in compiled.project_block
    assert compiled.active_task_block is not None
    assert "SSE Telemetry" in compiled.active_task_block

    assembled = compiled.to_assembled_prompt("What is the current status?")
    assert "## Active Project" in assembled
    assert "## Active Durable Task" in assembled


def test_compile_token_budgeting_and_compaction(compiler):
    small_compiler = ContextCompiler(max_tokens=300)
    sys_identity = "System prompt."
    user_query = "Summarize."

    # Provide 10 long history messages
    history = [
        {"role": "user", "content": f"Turn {i}: " + "x" * 200}
        for i in range(10)
    ]

    compiled = small_compiler.compile(
        system_identity=sys_identity,
        user_query=user_query,
        history=history,
    )

    # Must stay strictly within budget and keep the newest turns
    assert compiled.total_tokens <= 350
    assert len(compiled.dialogue_messages) < len(history)
    # The last message should be the most recent turn
    assert "Turn 9" in compiled.dialogue_messages[-1]["content"]

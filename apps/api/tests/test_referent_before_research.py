from hinaa_api.config import Settings
from hinaa_api.dialogue_state import (
    ConversationTurnState,
    build_semantic_turn_frame,
)
from hinaa_api.services import ConversationService


def test_ungrounded_referent_fresh_session():
    # Fresh session with no active topic or entity
    state = ConversationTurnState.empty(conversation_id="clean_session")
    
    frame = build_semantic_turn_frame("tell me more details about her", state)
    assert not frame.referent_resolved
    assert frame.clarification_prompt is not None
    assert "who" in frame.clarification_prompt.lower()
    
    # Verify service suppresses pre-search
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    service = ConversationService(settings)
    should_search = service._should_pre_search("tell me more details about her", d_state=state)
    assert not should_search, "Ungrounded referent must NOT trigger web search in fresh session"


def test_grounded_referent_with_active_state():
    # Session with Mikasa active
    state = ConversationTurnState.empty(conversation_id="active_mikasa_session")
    state.active_topic = "Mikasa Ackerman"
    state.active_entities = [{"name": "Mikasa Ackerman", "type": "character"}]
    
    frame = build_semantic_turn_frame("tell me more details about her", state)
    assert frame.referent_resolved
    assert "Mikasa Ackerman" in frame.referenced_subjects
    
    # Verify service allows search when grounded and asking for details
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    service = ConversationService(settings)
    should_search = service._should_pre_search("tell me more details about her", d_state=state)
    assert should_search, "Grounded referent with details request should be allowed to pre-search"
    
    # Check extracted query resolves to Mikasa
    query = service._extract_search_query("tell me more details about her", d_state=state)
    assert "Mikasa" in query


def test_explicit_subject_always_resolved():
    state = ConversationTurnState.empty(conversation_id="clean_session")
    frame = build_semantic_turn_frame("what is the weather in Kathmandu today", state)
    assert frame.referent_resolved
    assert "Kathmandu" in frame.locations
    
    settings = Settings(HINAA_PROVIDER_MODE="mock", _env_file=None)
    service = ConversationService(settings)
    assert service._should_pre_search("what is the weather in Kathmandu today", d_state=state)

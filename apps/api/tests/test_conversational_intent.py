"""Tests for Phase 04: Conversational Intelligence & Intent Engine."""

import pytest
from hinaa_api.intelligence.intent_engine import (
    ConversationalIntentEngine,
    UserIntentCategory,
    RelationshipMode,
)


def test_intent_engine_isekai_disambiguation():
    engine = ConversationalIntentEngine()
    result = engine.analyze("What do you think about the Isekai genre? Which anime is your favorite?")
    assert result.category == UserIntentCategory.CULTURAL_CONCEPT
    assert "Isekai" in result.cultural_concept
    assert "reincarnation" in result.cultural_concept.lower()
    assert result.recommended_mode == RelationshipMode.COMPANION


def test_intent_engine_device_control():
    engine = ConversationalIntentEngine()
    result = engine.analyze("Launch BlueStacks emulator and tap screen at coordinate 500, 800 via ADB")
    assert result.category == UserIntentCategory.DEVICE_CONTROL
    assert result.requires_tools is True
    assert result.recommended_mode == RelationshipMode.AUTONOMOUS_OPERATOR


def test_intent_engine_coding_dev():
    engine = ConversationalIntentEngine()
    result = engine.analyze("Help me refactor this Python script to use pytest and fix the syntax error")
    assert result.category == UserIntentCategory.CODING_DEV
    assert result.recommended_mode == RelationshipMode.CO_PILOT


def test_intent_engine_research_grounded():
    engine = ConversationalIntentEngine()
    result = engine.analyze("What is the latest stock price of NVIDIA today?")
    assert result.category == UserIntentCategory.RESEARCH_GROUNDED
    assert result.requires_tools is True
    assert result.search_query is not None


def test_intent_engine_meta_inspection():
    engine = ConversationalIntentEngine()
    result = engine.analyze("What is your architecture and how is your system status?")
    assert result.category == UserIntentCategory.META_INSPECTION
    assert result.recommended_mode == RelationshipMode.ANALYST

"""Pytest suite for Multilingual Speech Normalizer & Code-Switching Engine."""

import pytest
from hinaa_api.voice.multilingual import LanguageClass, MultilingualNormalizer


def test_anime_and_isekai_normalization():
    inputs = [
        ("I love issekai anime stories", "I love Isekai Anime stories"),
        ("What is an isikai world?", "What is an Isekai world?"),
        ("She is an otaku and loves manga", "She is an Otaku and loves manga"),
        ("Are you into shonun anime?", "Are you into Shonen anime?"),
        ("Can you find me an isecai show?", "Can you find me an Isekai show?"),
    ]
    for inp, expected in inputs:
        normalized = MultilingualNormalizer.normalize_transcript(inp)
        assert "Isekai" in normalized or "Otaku" in normalized or "Shonen" in normalized


def test_tech_and_developer_normalization():
    inputs = [
        ("Using fast api with python", "FastAPI"),
        ("The type script frontend is fast", "TypeScript"),
        ("Running blue stacks emulator", "BlueStacks"),
        ("Fine tune with q lora and lo ra", "QLoRA"),
        ("Connect via a d b bridge", "ADB"),
        ("Deploy with olama models", "Ollama"),
    ]
    for inp, expected_token in inputs:
        normalized = MultilingualNormalizer.normalize_transcript(inp)
        assert expected_token in normalized


def test_nepali_and_hindi_conversational_normalization():
    # Romanized Nepali phrases
    assert "सञ्चै छौ" in MultilingualNormalizer.normalize_transcript("sanchai chau hinaa")
    assert "के छ" in MultilingualNormalizer.normalize_transcript("k cha bro")
    assert "धन्यवाद" in MultilingualNormalizer.normalize_transcript("dhanyabad for the help")

    # Hindi phrases
    assert "क्या हाल है" in MultilingualNormalizer.normalize_transcript("kya haal hai hinaa")
    assert "शुक्रिया" in MultilingualNormalizer.normalize_transcript("shukriya dost")


def test_language_detection():
    # English
    assert MultilingualNormalizer.detect_dominant_language("Build a React dashboard") == LanguageClass.ENGLISH

    # Nepali (Devanagari)
    assert MultilingualNormalizer.detect_dominant_language("नमस्ते हिना, तिमीलाई कस्तो छ?") == LanguageClass.NEPALI

    # Hindi (Devanagari)
    assert MultilingualNormalizer.detect_dominant_language("नमस्ते, क्या हाल है आपका?") == LanguageClass.HINDI

    # Romanized code-switching
    assert MultilingualNormalizer.detect_dominant_language("sanchai chau timi?") == LanguageClass.NEPALI
    assert MultilingualNormalizer.detect_dominant_language("kya haal hai aapka?") == LanguageClass.HINDI


def test_tts_pronunciation_respelling():
    respelled = MultilingualNormalizer.prepare_tts_pronunciation("HINAA explains Isekai using FastAPI and QLoRA")
    assert "Hee-nah" in respelled
    assert "Ee-seh-kai" in respelled
    assert "fast A P I" in respelled
    assert "Q-LoRA" in respelled

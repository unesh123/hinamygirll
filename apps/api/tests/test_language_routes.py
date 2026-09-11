from hinaa_api.models import SpeechRequest, TurnRequest
from hinaa_api.prompts.language import language_hint
from hinaa_api.voice_profiles import resolve_voice


def test_nepali_contract_and_voice_route():
    assert TurnRequest(sessionId="nepali", text="नमस्ते", language="ne-NP").language == "ne-NP"
    assert SpeechRequest(text="नमस्ते", language="ne-NP").language == "ne-NP"
    assert "Nepali" in language_hint("ne-NP")
    assert resolve_voice("hinaa", "hi-IN-SwaraNeural", "hi-IN-MadhurNeural", "ne-NP") == "ne-NP-HemkalaNeural"
    assert resolve_voice("hinaa", "hi-IN-SwaraNeural", "hi-IN-MadhurNeural", "en-US") == "en-US-JennyNeural"
    assert resolve_voice("hinaa", "hi-IN-Custom", "hi-IN-MadhurNeural", "hi-IN") == "hi-IN-Custom"

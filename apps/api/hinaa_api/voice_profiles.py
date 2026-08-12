from __future__ import annotations

from dataclasses import dataclass

from .models import CompanionId, VoiceCalibration, VoiceProfile


@dataclass(frozen=True, slots=True)
class VoiceTuning:
    rate: float
    pitch_semitones: float
    volume: float


CALIBRATIONS: dict[str, VoiceTuning] = {
    "natural": VoiceTuning(1.0, 0.0, 1.0),
    "soft": VoiceTuning(0.94, -0.5, 0.9),
    "lively": VoiceTuning(1.07, 0.8, 1.0),
}


def resolve_voice(companion_id: CompanionId, female: str, male: str) -> str:
    return female if companion_id == "hinaa" else male


def resolve_calibration(value: str) -> VoiceTuning:
    return CALIBRATIONS.get(value, CALIBRATIONS["natural"])


def public_profiles(female: str, male: str) -> list[VoiceProfile]:
    disclosure = (
        "A standard Azure Hindi neural voice, not a custom anime or cloned identity. "
        "A unique character voice requires a licensed, consenting voice actor or approved dataset."
    )
    calibrations = [
        VoiceCalibration(
            id=key,
            label=key.title(),
            rate=CALIBRATIONS[key].rate,
            pitchSemitones=CALIBRATIONS[key].pitch_semitones,
            volume=CALIBRATIONS[key].volume,
        )
        for key in ("natural", "soft", "lively")
    ]
    return [
        VoiceProfile(
            companionId="hinaa",
            provider="azure-speech",
            requestedVoice=female,
            locale="hi-IN",
            identityDisclosure=disclosure,
            calibrations=calibrations,
        ),
        VoiceProfile(
            companionId="hiro",
            provider="azure-speech",
            requestedVoice=male,
            locale="hi-IN",
            identityDisclosure=disclosure,
            calibrations=calibrations,
        ),
    ]

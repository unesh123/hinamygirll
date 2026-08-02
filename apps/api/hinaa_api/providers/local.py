from __future__ import annotations

import asyncio
import shlex
import tempfile
from pathlib import Path
from time import perf_counter

from ..audio import pcm_to_wav, synthesize_placeholder_wav, validate_wav
from ..config import Settings
from ..errors import HinaaError
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts import PromptPackage, build_plan_from_text
from ..prompts.depth import infer_response_depth
from .base import ProviderResult


def _split_command(command: str) -> list[str]:
    return shlex.split(command)


def _command_error(kind: str) -> HinaaError:
    return HinaaError(
        f"LOCAL_{kind}_FAILED",
        f"Local {kind.lower()} engine failed safely. Check the local command configuration.",
        503,
        retryable=True,
        user_action_required=True,
    )


def _local_answer(text: str, companion_id: CompanionId, language: Language) -> str:
    lowered = text.lower()
    name = "Hiro" if companion_id == "hiro" else "Hinaa"
    if "stress" in lowered or "sad" in lowered or "थाक" in text:
        return (
            f"{name} local mode bata yahi cha. Aba 30 seconds slow breath, "
            "then one tiny next step choose garum. Perfect huna pressure chaina; "
            "steady huna enough cha."
        )
    if "motivation" in lowered or "message" in lowered or "प्रेर" in text:
        return (
            "Aaja ko short message: sano step pani real progress ho. "
            "Phone side rakha, ek task choose gara, ani 15 minutes HINAA-style focus."
        )
    if language == "en-US":
        return (
            "I am running in zero-credit local mode. I can help with text and safe "
            "placeholder voice now; "
            "real Nepali local speech needs offline STT/TTS engines next."
        )
    return (
        "Ma zero-credit local mode ma chaliraki chu. Text brain ra safe placeholder voice "
        "ready cha; "
        "real Nepali local STT/TTS ko lagi offline model bridge next step ho, bro."
    )


class LocalLLMProvider:
    id = "local-zero-credit-llm-v1"

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        started = perf_counter()
        depth = prompt.response_depth if prompt is not None else infer_response_depth(text, "rest")
        answer = _local_answer(text, companion_id, language)
        if history:
            answer = "Recent context yaad rakhera: " + answer
        plan = build_plan_from_text(
            text=answer,
            companion_id=companion_id,
            language="mixed" if language == "mixed" else language,
            depth=depth,
        )
        return ProviderResult(plan, self.id, int((perf_counter() - started) * 1000))


class LocalSTTProvider:
    def __init__(self, command: str | None, timeout_seconds: float) -> None:
        self.command = command.strip() if command else None
        self.timeout_seconds = timeout_seconds

    @property
    def id(self) -> str:
        return "local-command-stt-v1" if self.command else "local-stt-unconfigured-v1"

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]:
        if not self.command:
            raise HinaaError(
                "LOCAL_STT_UNAVAILABLE",
                "Zero-credit local speech recognition is not installed yet. "
                "Use text or mock voice mode.",
                503,
                retryable=False,
                user_action_required=True,
            )
        started = perf_counter()
        with tempfile.TemporaryDirectory(prefix="hinaa-local-stt-") as directory:
            input_path = Path(directory) / "input.wav"
            input_path.write_bytes(pcm_to_wav(pcm))
            command = [
                part.format(input=str(input_path), language=language)
                for part in _split_command(self.command)
            ]
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                stdout, _ = await asyncio.wait_for(process.communicate(), self.timeout_seconds)
            except TimeoutError as error:
                process.kill()
                await process.wait()
                raise _command_error("STT") from error
            if process.returncode != 0:
                raise _command_error("STT")
            text = stdout.decode("utf-8", errors="replace").strip()
            if not text:
                raise HinaaError("AUDIO_NO_SIGNAL", "No speech was recognized.", 422, True)
            return ProviderResult(text, self.id, int((perf_counter() - started) * 1000))


class LocalTTSProvider:
    def __init__(self, command: str | None, timeout_seconds: float) -> None:
        self.command = command.strip() if command else None
        self.timeout_seconds = timeout_seconds

    @property
    def id(self) -> str:
        return "local-command-tts-v1" if self.command else "local-placeholder-tts-v1"

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        started = perf_counter()
        if self.command:
            with tempfile.TemporaryDirectory(prefix="hinaa-local-tts-") as directory:
                output_path = Path(directory) / "output.wav"
                command = [
                    part.format(text=text, voice=voice, output=str(output_path))
                    for part in _split_command(self.command)
                ]
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await asyncio.wait_for(process.wait(), self.timeout_seconds)
                except TimeoutError as error:
                    process.kill()
                    await process.wait()
                    raise _command_error("TTS") from error
                if process.returncode != 0 or not output_path.exists():
                    raise _command_error("TTS")
                audio = output_path.read_bytes()
                validate_wav(audio, max_seconds=30)
                return ProviderResult(audio, self.id, int((perf_counter() - started) * 1000))
        voice_style = "hiro" if "Sagar" in voice or "hiro" in voice.lower() else "hinaa"
        return ProviderResult(
            synthesize_placeholder_wav(text, voice_style=voice_style),
            self.id,
            int((perf_counter() - started) * 1000),
        )


def make_local_stt(settings: Settings) -> LocalSTTProvider:
    return LocalSTTProvider(settings.local_stt_command, settings.local_command_timeout_seconds)


def make_local_tts(settings: Settings) -> LocalTTSProvider:
    return LocalTTSProvider(settings.local_tts_command, settings.local_command_timeout_seconds)


__all__ = [
    "LocalLLMProvider",
    "LocalSTTProvider",
    "LocalTTSProvider",
    "make_local_stt",
    "make_local_tts",
]

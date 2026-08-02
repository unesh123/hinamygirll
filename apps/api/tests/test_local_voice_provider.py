from __future__ import annotations

import sys

import pytest

from hinaa_api.audio import synthesize_placeholder_wav
from hinaa_api.errors import HinaaError
from hinaa_api.providers.local import LocalSTTProvider, LocalTTSProvider


def test_hinaa_and_hiro_placeholder_voices_are_distinct() -> None:
    hinaa = synthesize_placeholder_wav("Namaste Hinaa", voice_style="hinaa")
    hiro = synthesize_placeholder_wav("Namaste Hiro", voice_style="hiro")

    assert hinaa[:4] == b"RIFF"
    assert hiro[:4] == b"RIFF"
    assert hinaa != hiro


async def test_local_stt_command_reads_wav_and_returns_stdout(tmp_path) -> None:
    script = tmp_path / "stt.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "assert Path(sys.argv[1]).read_bytes()[:4] == b'RIFF'\n"
        "print('namaste hina')\n",
        encoding="utf-8",
    )
    wav = synthesize_placeholder_wav("input", voice_style="hinaa")
    provider = LocalSTTProvider(f'"{sys.executable}" "{script}" {{input}}', 5)

    result = await provider.transcribe(wav[44:], "ne-NP")

    assert result.provider == "local-command-stt-v1"
    assert result.value == "namaste hina"


async def test_local_tts_command_writes_valid_wav(tmp_path) -> None:
    script = tmp_path / "tts.py"
    script.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "Path(sys.argv[3]).write_bytes(Path(sys.argv[1]).read_bytes())\n",
        encoding="utf-8",
    )
    source = tmp_path / "source.wav"
    source.write_bytes(synthesize_placeholder_wav("Namaste", voice_style="hiro"))
    provider = LocalTTSProvider(f'"{sys.executable}" "{script}" "{source}" {{voice}} {{output}}', 5)

    result = await provider.synthesize("ignored", "hiro")

    assert result.provider == "local-command-tts-v1"
    assert result.value[:4] == b"RIFF"


async def test_local_stt_unconfigured_fails_without_silent_mock() -> None:
    provider = LocalSTTProvider(None, 5)

    with pytest.raises(HinaaError) as error:
        await provider.transcribe(b"not-real-pcm", "ne-NP")

    assert error.value.code == "LOCAL_STT_UNAVAILABLE"

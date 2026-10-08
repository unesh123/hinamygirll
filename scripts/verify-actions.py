"""End-to-end verification of HINAA's action chain.

Phase A: what the intent gate sanctions for real owner phrases.
Phase B: dry-run execution of the desktop-touching tools, real execution of
         safe ones (terminal, local image pipeline).
Phase C: one real visible action — the Spotify search demo.

Messaging tools (WhatsApp etc.) are deliberately untouched.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
from pathlib import Path

os.environ["HINAA_COMPUTER_DRY_RUN"] = "1"  # nothing reaches the real desktop
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "apps" / "api"))

from hinaa_api.tools.intent_gate import sanction_tools  # noqa: E402

PHRASES = [
    ("play daft punk on spotify", {"media", "computer", "youtube"}),
    ("open netflix", {"computer", "browser"}),
    ("open vs code", {"computer"}),
    ("open kimi", {"computer", "browser"}),
    ("build me a website for my gym", {"website", "design"}),
    ("search the web for the best gaming laptops", {"search", "research", "browser"}),
    ("run python --version in the terminal", {"terminal"}),
    ("generate an image of a sunset over mountains", {"image"}),
    ("remind me to stretch at 6pm", {"reminder"}),
    ("open youtube and play lofi beats", {"youtube", "browser", "computer"}),
]


def phase_a() -> bool:
    print("── Phase A: intent routing ──")
    ok = True
    for text, expected_fragments in PHRASES:
        s = sanction_tools(text)
        allowed = sorted(s.allowed)
        joined = " ".join(allowed).lower()
        hit = any(f in joined for f in expected_fragments)
        mark = "✓" if hit else "✗"
        if not hit:
            ok = False
        print(f"{mark} {text!r:52} -> {allowed or ['(none)']}")
    return ok


async def phase_b() -> bool:
    print("\n── Phase B: execution (dry-run desktop, real terminal/image) ──")
    ok = True

    from hinaa_api.tools.computer_operator import NativeComputerOperator

    res = await NativeComputerOperator.open_application("netflix")
    print(f"{'✓' if res.success else '✗'} open netflix        success={res.success} verified={res.verified}")
    ok &= res.success

    res = await NativeComputerOperator.open_application("vs code")
    print(f"{'✓' if res.success else '✗'} open vs code        success={res.success} detail={res.detail[:60]!r}")
    ok &= res.success

    res = await NativeComputerOperator.media_control("search_and_play", query="daft punk")
    print(f"{'✓' if res.success else '✗'} spotify search/play success={res.success} detail={res.detail[:60]!r}")
    ok &= res.success

    from hinaa_api.tools.terminal_hands import execute_terminal_hands
    term = await execute_terminal_hands({"command": "python --version"})
    good = term["status"] == "success" and "Python" in (term["stdout"] + term["stderr"])
    print(f"{'✓' if good else '✗'} terminal python       status={term['status']} out={term['stdout'][:40]!r}")
    ok &= good

    # Local image pipeline (no provider key needed): upscale + relight a real PNG.
    from PIL import Image
    from hinaa_api.providers.magnific import MagnificProvider

    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (120, 80, 200)).save(buf, format="PNG")
    provider = MagnificProvider()
    resolved = type("R", (), {"bytes_data": buf.getvalue(), "mime_type": "image/png"})()
    up = await provider._local_upscale(resolved, 2, "")
    rl = await provider._local_relight(resolved, "golden hour sunset")
    good = up.asset_ref.id and rl.asset_ref.id
    print(f"{'✓' if good else '✗'} image upscale/relight providers={up.provider}, {rl.provider}")
    ok &= bool(good)
    return ok


async def phase_c() -> None:
    print("\n── Phase C: the one real visible action (Spotify search opens) ──")
    os.environ.pop("HINAA_COMPUTER_DRY_RUN", None)
    from hinaa_api.tools.computer_operator import NativeComputerOperator
    res = await NativeComputerOperator.open_application("https://open.spotify.com/search/daft%20punk")
    print(f"{'✓' if res.success else '✗'} REAL open spotify search  success={res.success} verified={res.verified}")
    print(f"  detail: {res.detail}")


async def main() -> None:
    a = phase_a()
    b = await phase_b()
    await phase_c()
    print("\nRESULT:", "routing+execution OK" if (a and b) else "SOME CHECKS FAILED")


if __name__ == "__main__":
    asyncio.run(main())

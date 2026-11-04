"""Read-only check: python scripts/check_comfyui_bridge.py [--workflow path]."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from hinaa_api.providers.local_comfyui import ComfyUIConfig, LocalComfyUIProvider


async def check(args) -> int:
    provider = LocalComfyUIProvider(ComfyUIConfig(base_url=args.base_url, workflow_path=args.workflow))
    try:
        result = await provider.workflow_readiness()
        print(json.dumps(result, indent=2))
        if result["ready"] and args.generate:
            generated = await provider.submit_prompt(
                prompt=args.prompt, seed=42, width=768, height=768,
                filename_prefix="HINAA_bridge_check", mode="fast",
            )
            print(json.dumps(generated.model_dump(), indent=2))
        return 0 if result["ready"] else 1
    finally:
        await provider._http.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8188")
    parser.add_argument("--workflow", help="Path to your exported API-format workflow")
    parser.add_argument("--generate", action="store_true", help="Explicitly queue one 768x768 test image and validate its download")
    parser.add_argument("--prompt", default="A peaceful mountain lake at sunrise, soft natural light")
    raise SystemExit(asyncio.run(check(parser.parse_args())))

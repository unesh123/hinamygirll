"""Run HINA's actual motion tool locally, without a model API or running web server.

python scripts/render_cinematic.py examples/motion/cinematic-typography.json demo.mp4
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))


async def main():
    from hinaa_api.tools.code_animation_tool import (
        RenderCodeAnimationParams,
        creative_asset_manager,
        render_code_animation_handler,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("composition", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--workspace", type=Path, default=ROOT)
    parser.add_argument("--audio", help="Path inside --workspace to the supplied song")
    parser.add_argument("--audio-start", type=float, default=0)
    parser.add_argument(
        "--reference", help="Workspace video to inspect for cut candidates"
    )
    parser.add_argument("--fps", type=int, default=60)
    parser.add_argument("--width", type=int, default=1080)
    parser.add_argument("--height", type=int, default=1920)
    parser.add_argument("--preview", action="store_true")
    args = parser.parse_args()
    result = await render_code_animation_handler(
        RenderCodeAnimationParams(
            title="HINA Cinematic Motion Studio",
            composition_json=json.loads(args.composition.read_text(encoding="utf-8")),
            workspace_root=str(args.workspace.resolve()),
            audio_path=args.audio,
            audio_start_seconds=args.audio_start,
            reference_path=args.reference,
            audio_preset="none",
            width=args.width,
            height=args.height,
            fps=args.fps,
            preview=args.preview,
        )
    )
    if result.get("status") != "success":
        raise RuntimeError(result)
    data = creative_asset_manager.get_asset_bytes(result["asset_id"], "default_tenant")
    if not data:
        raise RuntimeError("HINA returned no downloadable asset bytes")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    args.output.with_suffix(".receipt.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    asyncio.run(main())

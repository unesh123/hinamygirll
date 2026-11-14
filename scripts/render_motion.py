"""Render an editable Hina motion JSON locally: python scripts/render_motion.py spec.json output-dir."""
import asyncio
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"apps/api"))
from hinaa_api.creative.models import CreativeJobSpec, CreativeOperation
from hinaa_api.creative.motion import render_motion_frames, motion_frame
from hinaa_api.creative.providers.timeline_exporter import timeline_video_exporter
from hinaa_api.creative.assets.video_validation import validate_video


async def render(source, output):
    spec=CreativeJobSpec.model_validate_json(Path(source).read_text(encoding="utf-8"))
    if spec.operation != CreativeOperation.TIMELINE_EXPORT or not spec.motion_scenes:
        raise ValueError("A TIMELINE_EXPORT specification with motion_scenes is required.")
    target=Path(output);target.mkdir(parents=True,exist_ok=True)
    frames=await asyncio.to_thread(render_motion_frames,spec.motion_scenes,spec.width,spec.height,spec.fps)
    data,_=await timeline_video_exporter.render_timeline_to_mp4(frames,spec.width,spec.height,spec.fps)
    receipt=await asyncio.to_thread(validate_video,data,".mp4")
    (target/"motion.mp4").write_bytes(data)
    (target/"source.json").write_text(spec.model_dump_json(indent=2),encoding="utf-8")
    (target/"receipt.json").write_text(json.dumps(receipt,indent=2),encoding="utf-8")
    t=0
    for i,scene in enumerate(spec.motion_scenes):
        motion_frame(spec.motion_scenes,t+scene.duration/2,spec.width,spec.height).save(target/f"scene-{i+1}.png")
        t+=scene.duration
    (target/"preview.html").write_text('<!doctype html><meta charset="utf-8"><title>Hina Motion Preview</title><body style="background:#10131e;color:white;font:18px sans-serif;max-width:1000px;margin:40px auto"><h1>Hina Motion</h1><video controls loop style="width:100%" src="motion.mp4"></video><p>Editable scene specification: <a href="source.json">source.json</a></p><p>Code-rendered locally. No cloud video generator.</p>',encoding="utf-8")
    print(json.dumps({"output":str(target.resolve()),"validation":receipt}))


if __name__ == "__main__":
    asyncio.run(render(sys.argv[1],sys.argv[2]))

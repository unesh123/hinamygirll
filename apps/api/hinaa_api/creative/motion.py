"""Editable, deterministic motion scenes. No generated code execution or cloud API."""
from __future__ import annotations

import io
import math
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image, ImageDraw, ImageFont


class MotionScene(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=90)
    subtitle: str = Field(default="", max_length=180)
    label: str = Field(default="HINA / MOTION", max_length=40)
    duration: float = Field(default=4, ge=1, le=10)
    accent: str = Field(default="#9f8cff", pattern=r"^#[0-9a-fA-F]{6}$")
    layout: str = Field(default="orbit", pattern=r"^(orbit|bars|steps)$")


def _font(size: int):
    for path in ("C:/Windows/Fonts/segoeuib.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def motion_frame(scenes: list[MotionScene], time: float, width: int, height: int) -> Image.Image:
    elapsed = 0.0
    scene = scenes[-1]
    for item in scenes:
        scene = item
        if time < elapsed + item.duration:
            break
        elapsed += item.duration
    local = max(0, time - elapsed)
    progress = min(1, local / .85)
    ease = 1 - (1 - progress) ** 3
    scale = min(width / 960, height / 540)
    image = Image.new("RGB", (width, height), "#10131e")
    draw = ImageDraw.Draw(image)
    margin = int(48 * scale)
    accent = scene.accent
    draw.line((margin, height-margin, width-margin, height-margin), fill="#303448", width=2)
    draw.line((margin, height-margin, margin + int((width-2*margin)*min(1,time/sum(s.duration for s in scenes))), height-margin), fill=accent, width=3)
    draw.text((margin, margin), scene.label, font=_font(max(12,int(15*scale))), fill=accent)
    title_font = _font(max(16,int(44*scale)))
    # Fit/wrap long headings rather than clipping the canvas.
    def text_lines(text, font, max_width):
        lines, line = [], ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if line and draw.textlength(candidate,font=font) > max_width:
                lines.append(line);line=word
            else:line=candidate
        return lines+[line]
    y = int(height*.27 + (1-ease)*25*scale)
    for line in text_lines(scene.title,title_font,width*.59):
        draw.text((margin,y),line,font=title_font,fill="#f5f3ff")
        y += int(53*scale)
    font = _font(max(12,int(19*scale)))
    for line in text_lines(scene.subtitle,font,width*.56):
        draw.text((margin,y+int(22*scale)),line,font=font,fill="#a8b0c7")
        y += int(27*scale)
    cx,cy = int(width*.8),int(height*.48)
    radius = int(70*scale)
    if scene.layout == "orbit":
        draw.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),outline="#383b54",width=max(2,int(3*scale)))
        for i in range(3):
            angle = local*.7+i*math.tau/3
            x,y=cx+math.cos(angle)*radius,cy+math.sin(angle)*radius
            r=12*scale*ease
            draw.ellipse((x-r,y-r,x+r,y+r),fill=accent)
        draw.text((cx-24*scale,cy-20*scale),"H",font=_font(max(18,int(40*scale))),fill="white")
    else:
        for i in range(3):
            x=cx+(i-1)*40*scale
            amount=(35+i*27)*scale*max(0,min(1,(local-i*.15)/.8))
            y=cy+(i*16*scale if scene.layout=="steps" else 50*scale)
            draw.rounded_rectangle((x-13*scale,y-amount,x+13*scale,y+1),radius=5*scale,fill=accent)
    # Symmetric fade keeps hard scene boundaries out of the output.
    fade=min(1,local/.25,max(0,(scene.duration-local)/.25))
    return Image.blend(Image.new("RGB",image.size,"#10131e"),image,fade)


def render_motion_frames(scenes: list[MotionScene], width: int, height: int, fps: float) -> list[bytes]:
    duration=sum(s.duration for s in scenes)
    count=math.ceil(duration*fps)
    if not scenes or duration>30 or width*height>1280*720 or width%2 or height%2 or count>900:
        raise ValueError("Motion export requires even dimensions, up to 720p, 30 seconds and 900 frames.")
    frames=[]
    for i in range(count):
        buffer=io.BytesIO()
        motion_frame(scenes,i/fps,width,height).save(buffer,format="PNG")
        frames.append(buffer.getvalue())
    return frames

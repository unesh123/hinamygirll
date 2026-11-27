"""Deterministic pre/post tool guards enforced at the tool boundary."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

GuardFn = Callable[[str, dict[str, Any]], dict[str, Any]]
GUARDS: list[GuardFn] = []


def guard(fn: GuardFn) -> GuardFn:
    """Register a payload guard executed in order by apply_guards."""
    GUARDS.append(fn)
    return fn


def _iter_scene_containers(payload: dict[str, Any]) -> list[dict[str, Any]]:
    containers: list[dict[str, Any]] = []
    if isinstance(payload.get("scenes"), list):
        containers.append(payload)
    comp = payload.get("composition_json")
    if isinstance(comp, dict) and isinstance(comp.get("scenes"), list):
        containers.append(comp)
    return containers


@guard
def duration_cap(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Clamp total scene duration to <= 30.0s before validation at the tool boundary."""
    if (
        tool_name not in ("render_code_animation", "create_motion_video")
        or not isinstance(payload, dict)
    ):
        return payload
    for key in ("duration_seconds", "duration"):
        val = payload.get(key)
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            payload[key] = max(0.5, min(30.0, float(val)))

    for container in _iter_scene_containers(payload):
        scenes = [s for s in container.get("scenes", []) if isinstance(s, dict)]
        if not scenes:
            continue
        total = sum(float(s.get("duration", 0) or 0) for s in scenes)
        if total > 30.0 and total > 0:
            k = 30.0 / total
            for s in scenes:
                s["duration"] = round(float(s.get("duration", 0) or 0) * k, 6)
            drift = 30.0 - sum(float(s.get("duration", 0) or 0) for s in scenes)
            last_dur = float(scenes[-1].get("duration", 0) or 0) + drift
            scenes[-1]["duration"] = round(max(0.0, last_dur), 6)
        total_after = round(sum(float(s.get("duration", 0) or 0) for s in scenes), 6)
        if isinstance(container.get("accents"), list) and total_after > 0:
            container["accents"] = sorted({
                round(float(t), 6)
                for t in container["accents"]
                if isinstance(t, (int, float)) and 0.0 <= float(t) < total_after
            })
    return payload


@guard
def scale_floor(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Clamp keyframe scales to >= 0.05 before reaching schema validation."""
    if not isinstance(payload, dict):
        return payload
    for container in _iter_scene_containers(payload):
        for scene in container.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            for layer in scene.get("layers", []):
                if not isinstance(layer, dict):
                    continue
                for kf in layer.get("keyframes", []):
                    if isinstance(kf, dict) and isinstance(kf.get("scale"), (int, float)):
                        kf["scale"] = max(0.05, float(kf["scale"]))
    return payload


@guard
def layer_timing_guard(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Clamp layer timing and transition durations to fit inside their parent scene."""
    if (
        tool_name not in ("render_code_animation", "create_motion_video")
        or not isinstance(payload, dict)
    ):
        return payload
    for container in _iter_scene_containers(payload):
        for scene in container.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            sd_raw = scene.get("duration")
            if not isinstance(sd_raw, (int, float)) or sd_raw <= 0:
                continue
            sd = float(sd_raw)
            td = scene.get("transition_duration")
            if isinstance(td, (int, float)):
                scene["transition_duration"] = round(max(0.05, min(1.0, float(td), sd)), 6)
            for layer in scene.get("layers", []):
                if not isinstance(layer, dict):
                    continue
                start = max(0.0, float(layer.get("start", 0.0) or 0.0))
                if start >= sd:
                    start = 0.0
                layer["start"] = round(start, 6)
                if "duration" in layer and isinstance(layer["duration"], (int, float)):
                    if start + float(layer["duration"]) > sd:
                        layer["duration"] = round(max(0.0, sd - start), 6)
                if "end" in layer and isinstance(layer["end"], (int, float)):
                    end_v = float(layer["end"])
                    if end_v <= start or end_v > sd:
                        layer["end"] = round(sd, 6)
                end_raw = layer.get("end")
                base_end = float(end_raw) if isinstance(end_raw, (int, float)) else sd
                span = round(base_end - start, 6)
                if span > 0 and isinstance(layer.get("keyframes"), list):
                    for kf in layer["keyframes"]:
                        if isinstance(kf, dict) and isinstance(kf.get("time"), (int, float)):
                            kf["time"] = round(max(0.0, min(span, float(kf["time"]))), 6)
                if span > 0 and isinstance(layer.get("unit_times"), list):
                    layer["unit_times"] = sorted(
                        round(float(x), 6)
                        for x in layer["unit_times"]
                        if isinstance(x, (int, float)) and 0.0 <= float(x) < span
                    )
    return payload


def apply_guards(tool_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run all registered pre-tool payload guards sequentially."""
    for g in GUARDS:
        payload = g(tool_name, payload)
    return payload

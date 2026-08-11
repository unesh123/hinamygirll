"""
vmc_bridge.py — VSeeFace VMC Protocol → WebSocket bridge

VSeeFace sends face tracking data via UDP using the VMC (Virtual Motion Capture)
Protocol on port 39539. Browsers can't receive UDP, so this module:

1. Listens on UDP 127.0.0.1:39539 (asyncio UDP)
2. Parses VMC /VMC/Ext/Blendshape/Val OSC messages
3. Broadcasts parsed blendshape data to all connected WebSocket clients at /ws/vmc

Frontend connects to: ws://localhost:8000/ws/vmc
VSeeFace sends to:    udp://127.0.0.1:39539

VMC blendshape names map to VRM expression presets:
  Fcl_MTH_Open → MouthOpen (aa)
  Fcl_MTH_Joy  → MouthSmile (happy)
  Fcl_EYE_Close_L / _R → blink
  Fcl_BRW_Up_L / _R    → surprised
  Fcl_BRW_Angry_L / _R → angry
"""

from __future__ import annotations

import asyncio
import json
import logging
import struct
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger("hinaa.vmc")

# ── OSC packet parser ────────────────────────────────────────────────────────

def _pad4(n: int) -> int:
    """Round up to next multiple of 4."""
    return (n + 3) & ~3


def _parse_osc_string(data: bytes, offset: int) -> tuple[str, int]:
    """Parse a null-terminated, 4-byte-aligned OSC string."""
    end = data.index(b"\x00", offset)
    s = data[offset:end].decode("utf-8", errors="ignore")
    return s, _pad4(end + 1)


def _parse_osc_message(data: bytes) -> tuple[str, list[Any]] | None:
    """Parse a single OSC message. Returns (address, args) or None on error."""
    try:
        offset = 0
        address, offset = _parse_osc_string(data, offset)

        if offset >= len(data) or data[offset:offset + 1] != b",":
            return address, []

        type_tag_str, offset = _parse_osc_string(data, offset)
        type_tags = type_tag_str[1:]  # strip leading ','

        args: list[Any] = []
        for tag in type_tags:
            if tag == "f":
                val = struct.unpack_from(">f", data, offset)[0]
                args.append(float(val))
                offset += 4
            elif tag == "i":
                val = struct.unpack_from(">i", data, offset)[0]
                args.append(int(val))
                offset += 4
            elif tag == "s":
                s, offset = _parse_osc_string(data, offset)
                args.append(s)
            else:
                break  # unknown type tag — skip rest

        return address, args
    except Exception:
        return None


def _parse_osc_bundle(data: bytes) -> list[tuple[str, list[Any]]]:
    """Parse an OSC bundle or single message. Returns list of (address, args)."""
    if data[:8] == b"#bundle\x00":
        messages = []
        offset = 16  # skip #bundle + timetag
        while offset < len(data):
            size = struct.unpack_from(">i", data, offset)[0]
            offset += 4
            msg = _parse_osc_message(data[offset: offset + size])
            if msg:
                messages.append(msg)
            offset += size
        return messages
    else:
        msg = _parse_osc_message(data)
        return [msg] if msg else []


# ── Known VMC blendshape name → our key mapping ──────────────────────────────
# VSeeFace sends ARKit-style or VRM-style blendshape names depending on model.
# We normalize all of them to our FaceExpressions keys.

_BLEND_MAP: dict[str, str] = {
    # ── Mouth ──
    "Fcl_MTH_Open":       "mouthOpen",
    "mouthOpen":          "mouthOpen",
    "jawOpen":            "mouthOpen",
    "Fcl_MTH_Joy":        "mouthSmile",
    "mouthSmile":         "mouthSmile",
    "mouthSmileLeft":     "mouthSmile",
    "mouthSmileRight":    "mouthSmile",
    # ── Eyes ──
    "Fcl_EYE_Close_L":   "eyeBlinkL",
    "eyeBlinkLeft":      "eyeBlinkL",
    "Fcl_EYE_Close_R":   "eyeBlinkR",
    "eyeBlinkRight":     "eyeBlinkR",
    # ── Brows ──
    "Fcl_BRW_Up_L":      "browUpL",
    "browInnerUp":       "browUpL",
    "browOuterUpLeft":   "browUpL",
    "Fcl_BRW_Up_R":      "browUpR",
    "browOuterUpRight":  "browUpR",
    "Fcl_BRW_Angry_L":   "browDownL",
    "browDownLeft":      "browDownL",
    "Fcl_BRW_Angry_R":   "browDownR",
    "browDownRight":     "browDownR",
    # ── Cheeks ──
    "cheekPuff":         "cheekPuff",
    "cheekPuffLeft":     "cheekPuff",
    "cheekPuffRight":    "cheekPuff",
}

_ALL_KEYS = {"mouthOpen", "mouthSmile", "eyeBlinkL", "eyeBlinkR",
             "browUpL", "browUpR", "browDownL", "browDownR", "cheekPuff"}


# ── Bridge state ─────────────────────────────────────────────────────────────

class VMCBridge:
    """Singleton that holds UDP listener state and WebSocket client set."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._values: dict[str, float] = {k: 0.0 for k in _ALL_KEYS}
        self._bones: dict[str, list[float]] = {}
        # Eye open = 1 by default (not closed)
        self._values["eyeBlinkL"] = 1.0
        self._values["eyeBlinkR"] = 1.0
        self._udp_transport: asyncio.BaseTransport | None = None
        self._task: asyncio.Task[None] | None = None

    # ── WebSocket clients ────────────────────────────────────────────────────

    async def add_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        logger.info("VMC WebSocket client connected (total=%d)", len(self._clients))
        # Send current state immediately so frontend isn't stale
        await self._send_to(ws)

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("VMC WebSocket client disconnected (total=%d)", len(self._clients))

    async def _send_to(self, ws: WebSocket) -> None:
        try:
            await ws.send_text(json.dumps({"blendshapes": self._values, "bones": self._bones}))
        except Exception:
            pass

    async def _broadcast(self) -> None:
        if not self._clients:
            return
        payload = json.dumps({"blendshapes": self._values, "bones": self._bones})
        dead = set()
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    # ── UDP receiver ─────────────────────────────────────────────────────────

    def on_datagram(self, data: bytes) -> None:
        """Called by asyncio UDP protocol on every received packet."""
        updated = False
        for address, args in _parse_osc_bundle(data):
            if address == "/VMC/Ext/Blendshape/Val" and len(args) >= 2:
                name = str(args[0])
                value = float(args[1])
                mapped = _BLEND_MAP.get(name)
                if mapped:
                    self._values[mapped] = max(0.0, min(1.0, value))
                    updated = True
            elif address == "/VMC/Ext/Bone/Pos" and len(args) >= 8:
                # args: name, px, py, pz, qx, qy, qz, qw
                name = str(args[0])
                self._bones[name] = [float(args[4]), float(args[5]), float(args[6]), float(args[7])]
                updated = True

        if updated and self._clients:
            # Schedule broadcast without awaiting (we're in sync context)
            asyncio.get_event_loop().call_soon(
                lambda: asyncio.ensure_future(self._broadcast())
            )

    async def start_udp(self, port: int = 39539) -> None:
        """Start listening for VMC UDP packets."""
        if self._udp_transport is not None:
            return  # already running

        loop = asyncio.get_event_loop()
        bridge = self

        class _Protocol(asyncio.DatagramProtocol):
            def datagram_received(self, data: bytes, addr: Any) -> None:
                bridge.on_datagram(data)

            def error_received(self, exc: Exception) -> None:
                logger.warning("VMC UDP error: %s", exc)

        try:
            transport, _ = await loop.create_datagram_endpoint(
                _Protocol,
                local_addr=("127.0.0.1", port),
            )
            self._udp_transport = transport
            logger.info("VMC bridge listening on UDP 127.0.0.1:%d", port)
        except OSError as e:
            logger.warning("VMC bridge could not bind UDP port %d: %s", port, e)

    def stop(self) -> None:
        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None


# Singleton instance
vmc_bridge = VMCBridge()

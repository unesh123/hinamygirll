"""HINAA's singleton VMC UDP-to-WebSocket bridge.

The bridge owns one UDP receiver. A bound receiver is only *listening*; the
bridge reports *live* only while recent supported, externally sourced VMC data
is being received. Explicit diagnostic samples are marked synthetic and can
never appear as an ordinary VSeeFace live signal.
"""

from __future__ import annotations

import asyncio
from collections import deque
import json
import logging
import struct
import time
import uuid
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("hinaa.vmc")

STALE_AFTER_SECONDS = 1.5
RATE_WINDOW_SECONDS = 1.0
LIVE_MIN_PACKET_RATE = 3


def _pad4(n: int) -> int:
    """Round up to the next OSC four-byte boundary."""
    return (n + 3) & ~3


def _parse_osc_string(data: bytes, offset: int) -> tuple[str, int]:
    """Parse one null-terminated, four-byte-aligned OSC string."""
    end = data.index(b"\x00", offset)
    value = data[offset:end].decode("utf-8", errors="ignore")
    return value, _pad4(end + 1)


def _parse_osc_message(data: bytes) -> tuple[str, list[Any]] | None:
    """Parse a single OSC message, returning its address and supported args."""
    try:
        offset = 0
        address, offset = _parse_osc_string(data, offset)
        if offset >= len(data) or data[offset:offset + 1] != b",":
            return address, []
        type_tag_str, offset = _parse_osc_string(data, offset)
        args: list[Any] = []
        for tag in type_tag_str[1:]:
            if tag == "f":
                args.append(float(struct.unpack_from(">f", data, offset)[0]))
                offset += 4
            elif tag == "i":
                args.append(int(struct.unpack_from(">i", data, offset)[0]))
                offset += 4
            elif tag == "s":
                value, offset = _parse_osc_string(data, offset)
                args.append(value)
            else:
                break
        return address, args
    except Exception:
        return None


def _parse_osc_bundle(data: bytes) -> list[tuple[str, list[Any]]]:
    """Parse an OSC bundle or one OSC message; malformed members are skipped."""
    if data[:8] != b"#bundle\x00":
        message = _parse_osc_message(data)
        return [message] if message else []
    messages: list[tuple[str, list[Any]]] = []
    try:
        offset = 16  # '#bundle' and the 64-bit OSC time tag
        while offset < len(data):
            size = struct.unpack_from(">i", data, offset)[0]
            offset += 4
            if size <= 0 or offset + size > len(data):
                break
            message = _parse_osc_message(data[offset: offset + size])
            if message:
                messages.append(message)
            offset += size
    except Exception:
        return messages
    return messages


# VSeeFace senders differ by VRM version, ARKit bridge, and exporter. Keys below
# are parser support only; a channel is listed in diagnostics only once observed.
_BLEND_MAP: dict[str, str] = {
    "Fcl_MTH_Open": "mouthOpen", "mouthOpen": "mouthOpen", "jawOpen": "mouthOpen",
    "Fcl_MTH_A": "mouthA", "A": "mouthA", "mouthA": "mouthA",
    "Fcl_MTH_I": "mouthI", "I": "mouthI", "mouthI": "mouthI",
    "Fcl_MTH_U": "mouthU", "U": "mouthU", "mouthU": "mouthU",
    "Fcl_MTH_E": "mouthE", "E": "mouthE", "mouthE": "mouthE",
    "Fcl_MTH_O": "mouthO", "O": "mouthO", "mouthO": "mouthO",
    "Fcl_MTH_Joy": "mouthSmile", "Fcl_ALL_Joy": "mouthSmile",
    "mouthSmile": "mouthSmile", "mouthSmileLeft": "mouthSmile", "mouthSmileRight": "mouthSmile",
    "Fcl_EYE_Close_L": "eyeBlinkL", "Blink_L": "eyeBlinkL", "eyeBlinkLeft": "eyeBlinkL",
    "Fcl_EYE_Close_R": "eyeBlinkR", "Blink_R": "eyeBlinkR", "eyeBlinkRight": "eyeBlinkR",
    "Fcl_BRW_Up_L": "browUpL", "browInnerUp": "browUpL", "browOuterUpLeft": "browUpL",
    "Fcl_BRW_Up_R": "browUpR", "browOuterUpRight": "browUpR",
    "Fcl_BRW_Angry_L": "browDownL", "browDownLeft": "browDownL",
    "Fcl_BRW_Angry_R": "browDownR", "browDownRight": "browDownR",
    "Fcl_ALL_Angry": "angry", "angry": "angry",
    "Fcl_ALL_Sorrow": "sad", "sorrow": "sad", "sad": "sad",
    "Fcl_ALL_Fun": "relaxed", "fun": "relaxed", "relaxed": "relaxed",
    "cheekPuff": "cheekPuff", "cheekPuffLeft": "cheekPuff", "cheekPuffRight": "cheekPuff",
}

_INITIAL_VALUES = {
    "mouthOpen": 0.0, "mouthA": 0.0, "mouthI": 0.0, "mouthU": 0.0,
    "mouthE": 0.0, "mouthO": 0.0, "mouthSmile": 0.0,
    "eyeBlinkL": 1.0, "eyeBlinkR": 1.0,
    "browUpL": 0.0, "browUpR": 0.0, "browDownL": 0.0, "browDownR": 0.0,
    "cheekPuff": 0.0, "angry": 0.0, "sad": 0.0, "relaxed": 0.0,
}
_TRACKED_BODY_BONES = {"Hips", "Spine", "Chest", "UpperChest", "Neck", "Head", "LeftShoulder", "RightShoulder"}


class VMCBridge:
    """One receiver, one OSC parser, and one fan-out path for local VMC data."""

    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._values: dict[str, float] = dict(_INITIAL_VALUES)
        self._bones: dict[str, list[float]] = {}
        self._channels: set[str] = set()
        self._udp_transport: asyncio.BaseTransport | None = None
        self._receiver_instance_id = f"vmc-{uuid.uuid4()}"
        self._port = 39539
        self._last_packet_monotonic: float | None = None
        self._last_packet_timestamp: str | None = None
        self._last_source = "none"  # none | external | synthetic
        self._last_sender: str | None = None
        self._packet_times: deque[float] = deque(maxlen=240)
        self._packet_count = 0
        self._connection_attempts = 0
        self._sequence = 0

    @property
    def listening(self) -> bool:
        return self._udp_transport is not None

    def diagnostics(self) -> dict[str, Any]:
        """Return a compact, non-sensitive current tracking status."""
        now = time.monotonic()
        age_ms: int | None = None
        if self._last_packet_monotonic is not None:
            age_ms = max(0, int((now - self._last_packet_monotonic) * 1000))
        while self._packet_times and now - self._packet_times[0] > RATE_WINDOW_SECONDS:
            self._packet_times.popleft()
        fresh = age_ms is not None and age_ms < int(STALE_AFTER_SECONDS * 1000)
        packet_rate = len(self._packet_times)
        if not self.listening:
            state = "disconnected"
        elif fresh and self._last_source == "synthetic":
            state = "test"
        elif fresh and self._last_source == "external" and packet_rate >= LIVE_MIN_PACKET_RATE:
            # A genuine VSeeFace sender publishes continuously. This deliberately
            # rejects one-off UDP probes from being displayed as ordinary LIVE.
            state = "live"
        elif fresh:
            state = "listening"
        elif age_ms is not None:
            state = "stale"
        else:
            state = "listening"
        return {
            "state": state,
            "listening": self.listening,
            "receiverInstanceId": self._receiver_instance_id,
            "host": "127.0.0.1",
            "port": self._port,
            "lastPacketTimestamp": self._last_packet_timestamp,
            "packetAgeMs": age_ms,
            "packetRate": packet_rate,
            "liveMinPacketRate": LIVE_MIN_PACKET_RATE,
            "packetCount": self._packet_count,
            "detectedChannels": sorted(self._channels),
            "source": self._last_source,
            "sender": self._last_sender,
            "webSocketClients": len(self._clients),
            "connectionAttempts": self._connection_attempts,
            "staleAfterMs": int(STALE_AFTER_SECONDS * 1000),
            "sequence": self._sequence,
        }

    def _payload(self) -> str:
        return json.dumps({
            "blendshapes": self._values,
            "bones": self._bones,
            "tracking": self.diagnostics(),
        })

    async def add_client(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        logger.info("VMC WebSocket client connected (total=%d)", len(self._clients))
        await self._send_to(ws)

    def remove_client(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        logger.info("VMC WebSocket client disconnected (total=%d)", len(self._clients))

    async def _send_to(self, ws: WebSocket) -> None:
        try:
            await ws.send_text(self._payload())
        except Exception:
            self.remove_client(ws)

    async def _broadcast(self) -> None:
        if not self._clients:
            return
        payload = self._payload()
        dead: set[WebSocket] = set()
        for ws in self._clients:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.add(ws)
        self._clients -= dead

    def _record_packet(self, *, source: str, sender: str | None, channels: set[str]) -> None:
        now = time.monotonic()
        self._last_packet_monotonic = now
        self._last_packet_timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._last_source = source
        self._last_sender = sender
        self._packet_times.append(now)
        self._packet_count += 1
        self._channels.update(channels)
        self._sequence += 1

    def _apply_messages(
        self,
        messages: list[tuple[str, list[Any]]],
        *,
        source: str,
        sender: str | None,
    ) -> bool:
        updated = False
        channels: set[str] = set()
        for address, args in messages:
            if address == "/VMC/Ext/Blendshape/Val" and len(args) >= 2:
                mapped = _BLEND_MAP.get(str(args[0]))
                if mapped:
                    try:
                        self._values[mapped] = max(0.0, min(1.0, float(args[1])))
                    except (TypeError, ValueError):
                        continue
                    channels.add(f"expression:{mapped}")
                    updated = True
            elif address == "/VMC/Ext/Bone/Pos" and len(args) >= 8:
                name = str(args[0])
                try:
                    rotation = [float(args[4]), float(args[5]), float(args[6]), float(args[7])]
                except (TypeError, ValueError):
                    continue
                if all(abs(v) <= 1.1 for v in rotation):
                    self._bones[name] = rotation
                    if name in _TRACKED_BODY_BONES:
                        channels.add(f"bone:{name}")
                    updated = True
        if updated:
            self._record_packet(source=source, sender=sender, channels=channels)
        return updated

    def on_datagram(self, data: bytes, addr: tuple[str, int] | None = None) -> None:
        """Process external UDP data; malformed/unsupported traffic is ignored."""
        sender = addr[0] if addr else None
        if self._apply_messages(_parse_osc_bundle(data), source="external", sender=sender) and self._clients:
            asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(self._broadcast()))

    def inject_test_signal(self) -> dict[str, Any]:
        """Inject one explicit diagnostic sample without opening another UDP port."""
        messages = [
            ("/VMC/Ext/Blendshape/Val", ["Fcl_MTH_Open", 0.45]),
            ("/VMC/Ext/Blendshape/Val", ["Fcl_EYE_Close_L", 0.15]),
            ("/VMC/Ext/Blendshape/Val", ["Fcl_EYE_Close_R", 0.10]),
            ("/VMC/Ext/Blendshape/Val", ["Fcl_MTH_Joy", 0.20]),
        ]
        self._apply_messages(messages, source="synthetic", sender="HINAA diagnostic")
        if self._clients:
            asyncio.get_event_loop().call_soon(lambda: asyncio.ensure_future(self._broadcast()))
        return self.diagnostics()

    async def start_udp(self, port: int = 39539) -> None:
        """Bind the single local receiver; repeated calls are intentionally idempotent."""
        self._port = port
        if self._udp_transport is not None:
            return
        self._connection_attempts += 1
        loop = asyncio.get_event_loop()
        bridge = self

        class Protocol(asyncio.DatagramProtocol):
            def datagram_received(self, data: bytes, addr: tuple[str, int]) -> None:
                bridge.on_datagram(data, addr)

            def error_received(self, exc: Exception) -> None:
                logger.warning("VMC UDP error: %s", exc)

        try:
            transport, _ = await loop.create_datagram_endpoint(Protocol, local_addr=("127.0.0.1", port))
            self._udp_transport = transport
            logger.info("VMC bridge listening on UDP 127.0.0.1:%d", port)
        except OSError as exc:
            logger.warning("VMC bridge could not bind UDP port %d: %s", port, exc)

    def stop(self) -> None:
        if self._udp_transport:
            self._udp_transport.close()
            self._udp_transport = None


vmc_bridge = VMCBridge()

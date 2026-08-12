from __future__ import annotations

import json
from pathlib import Path
import struct
import time

from hinaa_api.avatar_assets import AvatarAssetService
from hinaa_api.vmc_bridge import VMCBridge


def _glb(document: dict[object, object]) -> bytes:
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    payload += b" " * ((-len(payload)) % 4)
    total = 12 + 8 + len(payload)
    return struct.pack("<4sII", b"glTF", 2, total) + struct.pack("<II", len(payload), 0x4E4F534A) + payload


def test_vmc_diagnostics_distinguish_listening_test_live_and_stale() -> None:
    bridge = VMCBridge()
    bridge._udp_transport = object()  # type: ignore[assignment]  # No real test listener required.
    assert bridge.diagnostics()["state"] == "listening"

    test = bridge.inject_test_signal()
    assert test["state"] == "test"
    assert test["source"] == "synthetic"
    assert "expression:mouthOpen" in test["detectedChannels"]

    for _ in range(3):
        bridge._apply_messages(
            [("/VMC/Ext/Blendshape/Val", ["Fcl_EYE_Close_L", 0.4])],
            source="external",
            sender="127.0.0.1",
        )
    live = bridge.diagnostics()
    assert live["state"] == "live"
    assert live["source"] == "external"
    assert live["packetRate"] >= live["liveMinPacketRate"]
    assert "expression:eyeBlinkL" in live["detectedChannels"]

    bridge._last_packet_monotonic = time.monotonic() - 2.0
    assert bridge.diagnostics()["state"] == "stale"


def test_vmc_eye_close_values_remain_closure_weights() -> None:
    bridge = VMCBridge()
    bridge._udp_transport = object()  # type: ignore[assignment]
    assert bridge._values["eyeBlinkL"] == 0.0
    assert bridge._values["eyeBlinkR"] == 0.0

    bridge._apply_messages(
        [
            ("/VMC/Ext/Blendshape/Val", ["Fcl_EYE_Close_L", 0.25]),
            ("/VMC/Ext/Blendshape/Val", ["Fcl_EYE_Close_R", 0.70]),
        ],
        source="external",
        sender="127.0.0.1",
    )
    payload = json.loads(bridge._payload())
    assert payload["blendshapes"]["eyeBlinkL"] == 0.25
    assert payload["blendshapes"]["eyeBlinkR"] == 0.70


def test_vrm0_is_candidate_and_vrm1_is_not_vseeface_compatible(tmp_path: Path) -> None:
    service = AvatarAssetService(tmp_path / "workspace", tmp_path / "project")
    vrm0 = tmp_path / "candidate.vrm"
    vrm0.write_bytes(_glb({
        "extensions": {
            "VRM": {
                "humanoid": {"humanBones": [{"bone": "head", "node": 0}, {"bone": "chest", "node": 1}]},
                "blendShapeMaster": {"blendShapeGroups": [{"presetName": "A"}, {"presetName": "Blink"}]},
                "meta": {"licenseName": "CC0", "author": "Unesh"},
            }
        }
    }))
    metadata0 = service.inspect_file(vrm0)
    assert metadata0["vrmVersion"] == "0.x"
    assert metadata0["humanoidPresent"] is True
    assert metadata0["vseeFaceCompatibility"] == "compatible_candidate"
    assert metadata0["mouthExpressions"] == ["A"]

    vrm1 = tmp_path / "browser-only.vrm"
    vrm1.write_bytes(_glb({
        "extensions": {
            "VRMC_vrm": {
                "humanoid": {"humanBones": {"head": {"node": 0}}},
                "expressions": {"preset": {"aa": {}}},
                "meta": {"authors": ["Unesh"]},
            }
        }
    }))
    metadata1 = service.inspect_file(vrm1)
    assert metadata1["vrmVersion"] == "1.0"
    assert metadata1["vseeFaceCompatibility"] == "incompatible"
    assert "not represented as VSeeFace compatible" in metadata1["reason"]

"""
HINAA Enterprise Device Fleet Management Plane.

Manages multi-device desktop control:
- Device registration, capability inventories, heartbeats, and health telemetry.
- Prevents unrestricted remote access while coordinating authorized tasks.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DeviceNode(BaseModel):
    device_id: str
    name: str
    os_platform: str  # "Windows 11", "macOS Sonoma", "Ubuntu 24.04"
    agent_version: str = "0.9.8"
    capabilities: List[str] = Field(default_factory=lambda: ["desktop_control", "browser_automation"])
    status: str = "online"  # "online", "degraded", "offline"
    policy_version: str = "2.4.1"
    last_heartbeat: float = Field(default_factory=time.time)
    current_tasks_count: int = 0


class DeviceFleetManager:
    """
    Fleet controller tracking companion devices across an organization.
    """

    def __init__(self) -> None:
        self._devices: Dict[str, DeviceNode] = {}

    def register_device(self, device: DeviceNode) -> None:
        self._devices[device.device_id] = device
        logger.info("Registered companion device '%s' (%s)", device.name, device.device_id)

    def record_heartbeat(self, device_id: str, tasks_count: int = 0) -> bool:
        if device_id in self._devices:
            dev = self._devices[device_id]
            dev.last_heartbeat = time.time()
            dev.current_tasks_count = tasks_count
            dev.status = "online"
            return True
        return False

    def get_device(self, device_id: str) -> Optional[DeviceNode]:
        return self._devices.get(device_id)

    def list_healthy_devices(self, required_capability: Optional[str] = None) -> List[DeviceNode]:
        now = time.time()
        healthy: List[DeviceNode] = []
        for dev in self._devices.values():
            # Device considered offline if no heartbeat for 60 seconds
            if now - dev.last_heartbeat > 60.0:
                dev.status = "offline"
                continue

            if required_capability and required_capability not in dev.capabilities:
                continue

            healthy.append(dev)
        return healthy


_global_fleet_manager: Optional[DeviceFleetManager] = None


def get_fleet_manager() -> DeviceFleetManager:
    global _global_fleet_manager
    if _global_fleet_manager is None:
        _global_fleet_manager = DeviceFleetManager()
        # Seed local primary device
        _global_fleet_manager.register_device(
            DeviceNode(
                device_id="dev_local_primary",
                name="Primary Windows Workstation",
                os_platform="Windows 11",
                capabilities=["desktop_control", "browser_automation", "terminal", "audio_visemes"],
            )
        )
    return _global_fleet_manager

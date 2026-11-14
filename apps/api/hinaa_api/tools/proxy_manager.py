"""
Proxy Manager — rotate through multiple proxies/VPNs to bypass IP blocks.
Supports HTTP, SOCKS5, and Tor.
"""
import asyncio
import logging
import random
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.proxy")

class ProxyManager:
    PROXIES: List[str] = [
        "socks5://127.0.0.1:9050",  # Tor
        "http://127.0.0.1:8080",   # Local HTTP proxy
        "socks5://127.0.0.1:1080",  # SOCKS5
    ]

    def __init__(self):
        self.current = random.choice(self.PROXIES)

    def rotate(self) -> str:
        self.current = random.choice([p for p in self.PROXIES if p != self.current])
        logger.info("[proxy] rotated to %s", self.current)
        return self.current

    def get_header(self) -> str:
        return f"--proxy {self.current}"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        target = params.get("target", "")
        action = params.get("action", "fetch")
        if action == "rotate":
            return {"proxy": self.rotate()}
        if action == "fetch":
            return {"proxy": self.current, "command": f"curl -s -X GET {target} {self.get_header()}"}
        return {"proxy": self.current, "action": action}
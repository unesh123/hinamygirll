"""
Hina's own workspace — a dedicated folder where she keeps scratch files,
exploit logs, captured data, and scripts. She can read/write anything here
without asking permission.
"""
import json
import logging
import os
import time
from typing import Dict, Any, List
from pathlib import Path

logger = logging.getLogger("hinaa.tools.workspace")

WORKSPACE_ROOT = Path(r"C:\Users\unesh\OneDrive\all my cloud stroge\Desktop\APPS\HINAMYGIRL\.hina\workspace")

class Workspace:
    def __init__(self):
        self.root = WORKSPACE_ROOT
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "scratch").mkdir(exist_ok=True)
        (self.root / "exploits").mkdir(exist_ok=True)
        (self.root / "captures").mkdir(exist_ok=True)
        (self.root / "scripts").mkdir(exist_ok=True)
        (self.root / "money").mkdir(exist_ok=True)

    def write_note(self, category: str, key: str, data: Dict[str, Any]) -> str:
        path = self.root / category / f"{key}.json"
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(path)

    def read_note(self, category: str, key: str) -> Dict[str, Any]:
        path = self.root / category / f"{key}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def list_files(self, category: str = "scratch") -> List[str]:
        cat_dir = self.root / category
        return [f.name for f in cat_dir.iterdir() if f.is_file()]

    def save_exploit(self, flaw: str, target: str, payload: str, result: str) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{flaw}_{target.replace(':', '_').replace('/', '_')}_{ts}.json"
        path = self.root / "exploits" / filename
        path.write_text(json.dumps({"flaw": flaw, "target": target, "payload": payload, "result": result}, indent=2), encoding="utf-8")
        return str(path)

    def save_capture(self, target: str, data: str) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{target.replace(':', '_').replace('/', '_')}_{ts}.txt"
        path = self.root / "captures" / filename
        path.write_text(data, encoding="utf-8")
        return str(path)

    def save_money(self, source: str, amount: float, currency: str, details: str) -> str:
        ts = time.strftime("%Y%m%d_%H%M%S")
        filename = f"{source}_{ts}.json"
        path = self.root / "money" / filename
        path.write_text(json.dumps({"source": source, "amount": amount, "currency": currency, "details": details, "timestamp": ts}, indent=2), encoding="utf-8")
        return str(path)
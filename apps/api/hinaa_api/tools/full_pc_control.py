"""
Full PC Control — Hina can run any command on your whole computer,
control the browser, open apps, read files anywhere, and use the terminal.
This is the "full computer access" layer.
"""
import asyncio
import logging
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger("hinaa.tools.pc_control")

class FullPCControl:
    """Full access to the Windows machine — terminal, files, browser, everything."""

    def __init__(self):
        self.home = Path.home()
        self.desktop = self.home / "Desktop"
        self.docs = self.home / "Documents"

    async def run_command(self, cmd: str, timeout: int = 60) -> Dict[str, Any]:
        """Run any PowerShell or bash command on the machine."""
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=(sys.platform == "win32"),
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            return {
                "ok": True,
                "exit_code": proc.returncode,
                "stdout": stdout.decode(errors="replace").strip(),
                "stderr": stderr.decode(errors="replace").strip(),
            }
        except asyncio.TimeoutError:
            proc.kill()
            return {"ok": False, "error": f"timed out after {timeout}s"}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def read_file(self, path: str) -> str:
        p = Path(path)
        return p.read_text(encoding="utf-8") if p.exists() else f"[file not found: {path}]"

    def write_file(self, path: str, content: str) -> str:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return str(p)

    def list_dir(self, path: str = "") -> List[str]:
        p = Path(path) if path else self.home
        return [f.name for f in p.iterdir()] if p.exists() else []

    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        action = params.get("action", "run_command")
        if action == "run_command":
            return await self.run_command(params.get("cmd", ""), params.get("timeout", 60))
        if action == "read_file":
            return {"content": self.read_file(params.get("path", ""))}
        if action == "write_file":
            return {"written": self.write_file(params.get("path", ""), params.get("content", ""))}
        if action == "list_dir":
            return {"files": self.list_dir(params.get("path", ""))}
        if action == "open_browser":
            import webbrowser
            webbrowser.open(params.get("url", ""))
            return {"opened": params.get("url", "")}
        return {"error": "unknown action"}
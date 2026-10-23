"""Keep Hina's API, web preview, and optional public tunnel running.

Only child processes created by this runner are terminated. Public recovery
deploys the existing prebuilt web assets, never unreviewed working-tree edits.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / ".runtime" / "live"
API = ROOT / "apps" / "api"
WEB = ROOT / "apps" / "web"
site_packages = API / ".venv" / "Lib" / "site-packages"
if site_packages.exists() and str(site_packages) not in sys.path:
    sys.path.insert(0, str(site_packages))
if str(API) not in sys.path:
    sys.path.insert(0, str(API))
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
DESKTOP_PORT = 8765


def probe(url: str, *, api: bool = False) -> bool:
    try:
        request = urllib.request.Request(url, headers={"bypass-tunnel-reminder": "true"})
        with urllib.request.urlopen(request, timeout=8 if url.startswith("https:") else 4) as response:
            if response.status != 200:
                return False
            if api:
                data = json.load(response)
                return data.get("service") == "hinaa-api" and data.get("status") == "ok"
            return b"HINAA" in response.read(4096)
    except (OSError, ValueError):
        return False


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            return True
    except OSError:
        return False


def is_pid_alive(pid: int | None) -> bool:
    """Verify if a process ID is actually running on the OS."""
    if not pid or pid <= 0:
        return False
    try:
        if os.name == "nt":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid)
            if not handle:
                return False
            exit_code = ctypes.c_ulong()
            success = kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
            kernel32.CloseHandle(handle)
            return bool(success and exit_code.value == 259)  # 259 is STILL_ACTIVE
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def clean_stale_runner_state(runtime_dir: Path) -> None:
    """Purge stale PIDs and dead runner status from runner-state.json."""
    state_file = runtime_dir / "runner-state.json"
    if not state_file.exists():
        return
    try:
        state = json.loads(state_file.read_text(encoding="utf-8"))
        runner_pid = state.get("runnerPid")
        # If the runner PID is dead or missing, clean stale process references
        if not runner_pid or not is_pid_alive(runner_pid):
            state["runnerPid"] = None
            state["status"] = "offline"
            state["processes"] = {}
            state["apiHealthy"] = port_open(8000)
            state["webHealthy"] = port_open(5173)
            state["tunnelHealthy"] = False
            state["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"Warning: could not clean stale runner state: {exc}", flush=True)


def desktop_probe() -> bool:
    """Prove the private desktop bridge is alive with its pairing token.

    A bare open port is not enough: another process could own 8765, and an
    unauthenticated response says nothing about Hina's actuator being usable.
    The token stays local and is never written to runner state or logs.
    """
    token_path = ROOT / ".runtime" / "desktop" / "bridge.token"
    try:
        token = token_path.read_text(encoding="utf-8").strip()
        if len(token) < 32:
            return False
        request = urllib.request.Request(
            f"http://127.0.0.1:{DESKTOP_PORT}/health",
            headers={"Authorization": "Bearer " + token, "User-Agent": "HINAA-Live-Runner"},
        )
        with urllib.request.urlopen(request, timeout=2) as response:
            data = json.load(response)
            return response.status == 200 and data.get("status") == "ready"
    except (OSError, ValueError):
        return False


def sanitize_path() -> None:
    """Drop PATH entries whose directory no longer exists.

    A bundled IDE/agent runtime used to ship its own node.exe; an app update
    deleted the binary but left the directory on PATH, so every child that
    resolved `node` through the shell died with '"…\\node.exe" is not
    recognized' and the public repoint deploy stalled forever. Children
    inherit this process's environment, so scrubbing here fixes every spawn.
    """
    entries = os.environ.get("PATH", "").split(os.pathsep)
    keep = [entry for entry in entries if entry and Path(entry).exists()]
    os.environ["PATH"] = os.pathsep.join(keep)


def tunnel_origin(path: Path) -> str | None:
    try:
        matches = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", path.read_text(errors="replace"))
        return matches[-1] if matches else None
    except OSError:
        return None


def repoint(origin: str) -> None:
    for path in (ROOT / "vercel.json", WEB / "vercel.json", ROOT / ".vercel/output/config.json"):
        if path.exists():
            original = path.read_text(encoding="utf-8")
            updated = re.sub(r"https://[a-z0-9-]+\.trycloudflare\.com", origin, original)
            if updated != original:
                path.write_text(updated, encoding="utf-8")


def public_environment() -> dict[str, str]:
    """Fail closed before a tunnel is created; never expose the dev profile."""
    from dotenv import dotenv_values
    api_config = {**dotenv_values(API / ".env.local"), **os.environ}
    web_config = {**dotenv_values(WEB / ".env.local"), **os.environ}
    owner_path = RUNTIME / "owner-id.txt"
    owner = owner_path.read_text().strip() if owner_path.exists() else ""
    if not re.fullmatch(r"user_[A-Za-z0-9]+(?:,\s*user_[A-Za-z0-9]+)*", owner):
        raise RuntimeError("A verified owner ID is required in .runtime/live/owner-id.txt.")
    if not api_config.get("CLERK_SECRET_KEY") or not web_config.get("VITE_CLERK_PUBLISHABLE_KEY"):
        raise RuntimeError("Configure existing Clerk keys before starting the private live site.")
    return {
        "HINAA_AUTH_MODE": "clerk", "HINAA_ALLOWED_USER_IDS": owner,
        "HINAA_PERSISTENCE_ENABLED": "true", "ENVIRONMENT": "production",
        "HINAA_ALLOW_TUNNEL_DEV_AUTH": "false", "HINAA_ALLOW_REMOTE_LOCAL_TOOLS": "false",
        # Provider benches survive a restart, so the first turn after one does
        # not pay the dead-primary hang again. Off in dev and under pytest.
        "HINAA_BREAKER_PERSISTENCE": "1",
        "CLERK_AUTHORIZED_PARTIES": "https://hinaa-workspace.vercel.app,http://127.0.0.1:5173,http://localhost:5173",
    }


class Runner:
    def __init__(self, public: bool, dev: bool, deploy: bool):
        self.public, self.dev, self.deploy = public, dev, deploy
        if deploy and not public:
            raise RuntimeError("--deploy requires --public.")
        if public and dev:
            raise RuntimeError("Public mode requires the reviewed production build.")
        self.public_env = public_environment() if public else {}
        if public:
            manifest_path = ROOT / ".vercel/output/hina-live-build.json"
            manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
            if manifest.get("authMode") != "clerk":
                raise RuntimeError("Prepare an authenticated production build before opening the tunnel.")
        self.children: dict[str, subprocess.Popen] = {}
        self.failures: dict[str, int] = {}
        self.retry_at: dict[str, float] = {}
        self.origin: str | None = None
        self.published: str | None = None
        self.desktop_healthy = False
        self.publish_retry = 0.0
        self.previous: dict = {}
        self.node = shutil.which("node")
        self.npx = Path(self.node).parent / "node_modules/npm/bin/npx-cli.js" if self.node else None
        # A bundled runtime node (IDE/agent tooling shipping its own copy) can
        # shadow the real install on PATH; it has no npm/npx beside it, so the
        # deploy check below would fail for the wrong reason. Fall back to the
        # standard install location before declaring Node missing.
        if self.node and not (self.npx and self.npx.exists()):
            for candidate in (Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs/node.exe",):
                probe_npx = candidate.parent / "node_modules/npm/bin/npx-cli.js"
                if candidate.exists() and probe_npx.exists():
                    self.node = str(candidate)
                    self.npx = probe_npx
                    break
        if not self.node:
            raise RuntimeError("Node.js was not found. Install Node before starting Hina.")
        # Pinned Vercel CLI installed once under tools/deploy. Preferred over
        # `npx --yes vercel`: the npx cache corrupts when a deploy attempt is
        # killed mid-install (EPERM on cleanup) and then every retry reinstalls
        # over locked files, so the public repoint never recovers.
        pinned_vercel = ROOT / "tools" / "deploy" / "node_modules" / "vercel" / "dist" / "index.js"
        self.vercel: Path | None = pinned_vercel if pinned_vercel.exists() else None
        if not dev and not (WEB / "dist/index.html").exists():
            raise RuntimeError("The web build is missing. Run pnpm --dir apps/web build first.")
        if public and not (ROOT / "cloudflared.exe").exists():
            raise RuntimeError("The configured cloudflared.exe is missing.")
        deploy_tool = self.vercel or (self.npx if self.npx and self.npx.exists() else None)
        if deploy and (not deploy_tool or not (ROOT / ".vercel/output/static/index.html").exists()):
            raise RuntimeError("Prepare the production assets before enabling automatic public recovery.")

    def start(self, name: str, command: list[str], cwd: Path, env: dict | None = None) -> None:
        if time.monotonic() < self.retry_at.get(name, 0):
            return
        with (RUNTIME / f"{name}.out.log").open("ab") as out, (RUNTIME / f"{name}.err.log").open("ab") as err:
            self.children[name] = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                                   stdout=out, stderr=err, creationflags=NO_WINDOW)
        (RUNTIME / f"{name}.pid").write_text(str(self.children[name].pid))
        self.retry_at[name] = time.monotonic() + 20
        print(f"Started {name} PID {self.children[name].pid}", flush=True)

    def stop(self, name: str) -> None:
        child = self.children.pop(name, None)
        if child is None or child.poll() is not None:
            return
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
        else:
            child.terminate()
        try:
            child.wait(timeout=8)
        except subprocess.TimeoutExpired:
            child.kill()

    def ensure(self, name: str, port: int, healthy: bool, command: list[str], cwd: Path, env=None) -> None:
        child = self.children.get(name)
        if child and child.poll() is not None:
            self.children.pop(name)
            child = None
        if healthy:
            self.failures[name] = 0
            return
        self.failures[name] = self.failures.get(name, 0) + 1
        if child and self.failures[name] >= 3 and time.monotonic() >= self.retry_at.get(name, 0):
            self.stop(name)
            child = None
        if child is None and not port_open(port):
            self.start(name, command, cwd, env)

    def tick(self) -> None:
        if self.public:
            if "api" not in self.children and port_open(8000):
                raise RuntimeError("Stop the existing local API before starting the private public runner.")
            tunnel = self.children.get("tunnel")
            tunnel_alive = tunnel is not None and tunnel.poll() is None and is_pid_alive(tunnel.pid)
            if not tunnel_alive and time.monotonic() >= self.retry_at.get("tunnel", 0):
                self.origin = None
                # Only the runner's own output is reset for a new tunnel.
                for suffix in ("out", "err"):
                    (RUNTIME / f"tunnel.{suffix}.log").write_text("")
                tunnel_token = os.environ.get("CLOUDFLARE_TUNNEL_TOKEN")
                token_path = RUNTIME / "tunnel.token"
                if not tunnel_token and token_path.exists():
                    tunnel_token = token_path.read_text(encoding="utf-8").strip()
                configured_origin = os.environ.get("CLOUDFLARE_TUNNEL_ORIGIN") or os.environ.get("HINAA_PUBLIC_API_ORIGIN")
                origin_path = RUNTIME / "tunnel.origin"
                if not configured_origin and origin_path.exists():
                    configured_origin = origin_path.read_text(encoding="utf-8").strip()

                if tunnel_token:
                    self.start("tunnel", [str(ROOT / "cloudflared.exe"), "tunnel", "run", "--token", tunnel_token], ROOT)
                    if configured_origin:
                        self.origin = configured_origin
                else:
                    self.start("tunnel", [str(ROOT / "cloudflared.exe"), "tunnel", "--url", "http://127.0.0.1:8000",
                                          "--no-autoupdate", "--protocol", "http2"], ROOT)
            candidate = tunnel_origin(RUNTIME / "tunnel.err.log") or tunnel_origin(RUNTIME / "tunnel.out.log")
            if candidate and candidate != self.origin:
                self.origin = candidate
                # Restart only an API owned by this runner to advertise the new
                # WebSocket origin. The local environment file is never edited.
                self.stop("api")
                self.retry_at["api"] = 0

        # Keep the loopback-only interactive actuator beside the API. It uses a
        # private bearer token and still sits behind the owner/session policy in
        # the API, so starting it does not grant the public site blanket access.
        self.desktop_healthy = desktop_probe()
        self.ensure(
            "desktop",
            DESKTOP_PORT,
            self.desktop_healthy,
            [str(API / ".venv/Scripts/python.exe"), str(ROOT / "scripts/hinaa_desktop_daemon.py")],
            ROOT,
        )

        api_ok = probe("http://127.0.0.1:8000/health/live", api=True)
        api_env = {**os.environ, **self.public_env}
        api_env["PYTHONPATH"] = str(API) + (os.pathsep + api_env["PYTHONPATH"] if "PYTHONPATH" in api_env else "")
        if self.origin:
            api_env["HINAA_REALTIME_PUBLIC_ORIGIN"] = self.origin
        self.ensure("api", 8000, api_ok, [str(API / ".venv/Scripts/python.exe"), "-m", "uvicorn",
                    "hinaa_api.main:app", "--host", "127.0.0.1", "--port", "8000"], API, api_env)
        web_ok = probe("http://127.0.0.1:5173/")
        web_command = [self.node, str(WEB / "node_modules/vite/bin/vite.js")]
        if not self.dev:
            web_command.append("preview")
        web_command += ["--host", "127.0.0.1", "--port", "5173", "--strictPort"]
        self.ensure("web", 5173, web_ok, web_command, WEB)
        tunnel_ok = bool(self.origin and api_ok and probe(f"{self.origin}/health/live", api=True))
        if self.public and self.origin and api_ok:
            self.failures["tunnel"] = 0 if tunnel_ok else self.failures.get("tunnel", 0) + 1
            if self.failures["tunnel"] >= 6:
                self.stop("tunnel")
                self.failures["tunnel"] = 0
                self.retry_at["tunnel"] = 0
        deploy_error = self.previous.get("deployError")
        if tunnel_ok and self.deploy and self.origin != self.published and time.monotonic() >= self.publish_retry:
            repoint(self.origin)
            self.write_state(api_ok, web_ok, tunnel_ok, "publishing", None)
            if self.vercel:
                deploy_command = [self.node, str(self.vercel)]
            else:
                deploy_command = [self.node, str(self.npx), "--yes", "vercel"]
            deploy_command += ["deploy", "--prebuilt", "--prod", "--yes", "--scope", "uneshs-projects"]
            with (RUNTIME / "deploy.log").open("ab") as log:
                result = subprocess.run(deploy_command,
                                        cwd=ROOT, stdout=log, stderr=log, timeout=240, creationflags=NO_WINDOW)
            if result.returncode == 0:
                self.published, deploy_error = self.origin, None
                print("Public site repointed to the healthy tunnel.", flush=True)
            else:
                deploy_error = "Deployment failed; inspect .runtime/live/deploy.log"
                self.publish_retry = time.monotonic() + 120
        public_ok = bool(self.published and probe("https://hinaa-workspace.vercel.app/health/live", api=True))
        self.write_state(api_ok, web_ok, tunnel_ok, "online" if public_ok else "starting" if self.public else "local", deploy_error)

    def write_state(self, api_ok, web_ok, tunnel_ok, status, error):
        tunnel_token = bool(os.environ.get("CLOUDFLARE_TUNNEL_TOKEN") or (RUNTIME / "tunnel.token").exists())
        active_processes = {k: v.pid for k, v in self.children.items() if v.poll() is None and is_pid_alive(v.pid)}
        state = {
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "runnerPid": os.getpid(),
            "status": status,
            "apiHealthy": api_ok,
            "webHealthy": web_ok,
            "tunnelHealthy": tunnel_ok,
            "desktopHealthy": self.desktop_healthy,
            "namedTunnel": tunnel_token,
            "heartbeatExpirySec": 10,
            "tunnelOrigin": self.origin,
            "publishedOrigin": self.published,
            "siteUrl": "https://hinaa-workspace.vercel.app" if self.public else "http://127.0.0.1:5173",
            "processes": active_processes,
            "deployError": error,
        }
        target = RUNTIME / "runner-state.json"
        content = json.dumps(state, indent=2)
        # Resilient atomic write with retries and direct write fallback on Windows
        for attempt in range(5):
            try:
                temporary = RUNTIME / f"runner-state.{os.getpid()}.tmp"
                temporary.write_text(content, encoding="utf-8")
                temporary.replace(target)
                self.previous = state
                return
            except OSError:
                time.sleep(0.05 * (attempt + 1))
        try:
            target.write_text(content, encoding="utf-8")
            self.previous = state
        except Exception as e:
            print(f"Warning: could not write runner-state: {e}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--public", action="store_true")
    parser.add_argument("--dev", action="store_true")
    parser.add_argument("--deploy", action="store_true", help="Recover public routing using prebuilt assets")
    args = parser.parse_args()
    RUNTIME.mkdir(parents=True, exist_ok=True)
    clean_stale_runner_state(RUNTIME)
    sanitize_path()
    # Exclusive OS file lock prevents two runners from fighting over ports.
    with (RUNTIME / "runner.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0); lock.write(b"0"); lock.flush(); lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise SystemExit("Hina's live runner is already active.")
        runner = Runner(args.public, args.dev, args.deploy)
        (RUNTIME / "runner.pid").write_text(str(os.getpid()))
        try:
            while not (RUNTIME / "stop-requested").exists():
                try:
                    runner.tick()
                except Exception as exc:
                    print(f"Runner check failed: {type(exc).__name__}: {exc}", flush=True)
                    runner.publish_retry = time.monotonic() + 60
                    try:
                        runner.write_state(False, False, False, "error", str(exc))
                    except Exception as err:
                        print(f"Failed to record error state: {err}", flush=True)
                time.sleep(3)
        finally:
            for name in list(runner.children):
                runner.stop(name)
            (RUNTIME / "stop-requested").unlink(missing_ok=True)
            (RUNTIME / "runner.pid").unlink(missing_ok=True)
            clean_stale_runner_state(RUNTIME)


if __name__ == "__main__":
    main()

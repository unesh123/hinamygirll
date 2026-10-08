"""Visual check: drive Hina through emotion scenarios and screenshot the avatar.

Usage: python scripts/visual-check.py [scenario ...]
Requires the live local app on http://localhost:5173 and the backend on :8000.
Screenshots land in visual-check/ at the repo root.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path("visual-check")
OUT.mkdir(exist_ok=True)

BASE_URL = os.environ.get("VISUAL_CHECK_URL", "http://localhost:5199")

SCENARIOS = {
    "shy": "Hina... can I tell you a secret? You're honestly the cutest part of my whole day. Don't get all flustered on me now.",
    "excited": "HINA!! WE DID IT!! The app went viral overnight — a million downloads!! Isn't that absolutely incredible?!",
    "sleepy": "sigh... I'm so exhausted, Hina. It's late, everything feels heavy, and I just want to rest. Stay with me?",
    "determined": "Alright Hina, listen — we have three hours to finish this entire project. No distractions, no excuses. I need you focused and locked in with me. Ready?",
    "nervous": "My big presentation starts in five minutes and my hands are shaking... I'm really nervous, Hina.",
}


def biggest_canvas_box(page):
    canvases = page.locator("canvas")
    best, best_area = None, 0
    for i in range(canvases.count()):
        c = canvases.nth(i)
        try:
            box = c.bounding_box()
        except Exception:
            continue
        if box and box["width"] * box["height"] > best_area:
            best, best_area = box, box["width"] * box["height"]
    return best


def wait_for_server(url: str, timeout_s: float = 90.0) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                if resp.status < 500:
                    return
        except Exception:
            time.sleep(1.5)
    raise RuntimeError(f"dev server at {url} did not come up in {timeout_s}s")


def start_authless_server() -> subprocess.Popen | None:
    """Spin a temporary Vite server with the Clerk gate disabled.

    Vite gives already-set process env vars priority over .env files, so
    VITE_HINAA_AUTH_MODE=off here wins without touching the project's env.
    """
    if os.environ.get("VISUAL_CHECK_URL"):
        return None  # caller manages the server
    env = {**os.environ, "VITE_HINAA_AUTH_MODE": "off"}
    proc = subprocess.Popen(
        ["cmd", "/c", "node_modules\\.bin\\vite.CMD", "--port", "5199", "--strictPort"],
        cwd=str(Path(__file__).resolve().parent.parent / "apps" / "web"),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    wait_for_server(BASE_URL)
    return proc


def main() -> None:
    names = [a for a in sys.argv[1:] if a in SCENARIOS] or list(SCENARIOS)
    server = start_authless_server()
    try:
        run_scenarios(names)
    finally:
        if server:
            server.terminate()
            try:
                server.wait(timeout=10)
            except Exception:
                server.kill()


def run_scenarios(names: list[str]) -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--autoplay-policy=no-user-gesture-required",
                "--enable-unsafe-swiftshader",
                "--mute-audio",
            ],
        )
        page = browser.new_page(viewport={"width": 1366, "height": 900})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.on(
            "request",
            lambda r: print(f"[req] {r.method} {r.url}", flush=True)
            if "/api/" in r.url
            else None,
        )
        page.goto(BASE_URL, wait_until="domcontentloaded")
        try:
            page.get_by_role("button", name="Enter your workspace").click(timeout=20_000)
            print("[gate] entered workspace", flush=True)
        except Exception:
            print("[gate] no welcome gate", flush=True)
        page.wait_for_selector("canvas", timeout=120_000)
        page.wait_for_timeout(10_000)  # model load + idle settle
        # Cycle the avatar camera to full body so arm/hand poses are visible.
        cam_btn = page.locator('button[aria-label^="Change avatar camera"]').first
        print(f"[cam] buttons found: {page.locator('button[aria-label^=\"Change avatar camera\"]').count()}", flush=True)
        for _ in range(4):
            try:
                label = cam_btn.get_attribute("aria-label", timeout=5_000) or ""
                print(f"[cam] label: {label}", flush=True)
            except Exception as exc:
                print(f"[warn] camera label: {type(exc).__name__}: {exc}", flush=True)
                break
            if "from full" in label:
                break
            try:
                cam_btn.evaluate("el => el.click()")
                page.wait_for_timeout(800)
            except Exception as exc:
                print(f"[warn] camera cycle failed: {type(exc).__name__}: {exc}", flush=True)
                break
        page.screenshot(path=str(OUT / "00_postgate_full.png"))
        box = biggest_canvas_box(page)
        if box:
            page.screenshot(path=str(OUT / "00_idle.png"), clip=box)
        page.screenshot(path=str(OUT / "00_idle_full.png"))

        composer = page.locator('[data-testid="composer-input"]')
        for name in names:
            msg = SCENARIOS[name]
            print(f"[scenario] {name}", flush=True)
            try:
                with page.expect_request(
                    lambda r: "/api/v1/speech/synthesis" in r.url, timeout=150_000
                ):
                    composer.fill(msg, timeout=15_000)
                    composer.press("Enter")
                    page.wait_for_timeout(2_000)
                    page.screenshot(path=str(OUT / f"{name}_after_enter.png"))
            except Exception as exc:
                print(f"[warn] no synthesis request for {name}: {type(exc).__name__}", flush=True)
            page.wait_for_timeout(5_000)
            box = biggest_canvas_box(page)
            if box:
                page.screenshot(path=str(OUT / f"{name}_a.png"), clip=box)
            page.wait_for_timeout(4_000)
            box = biggest_canvas_box(page)
            if box:
                page.screenshot(path=str(OUT / f"{name}_b.png"), clip=box)
            page.screenshot(path=str(OUT / f"{name}_full.png"))
            page.wait_for_timeout(8_000)  # let speech wind down before next turn
        browser.close()
    if errors:
        print("page errors:", errors[:5])
    print("done")


if __name__ == "__main__":
    main()

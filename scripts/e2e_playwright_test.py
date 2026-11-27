import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUTPUT_DIR = Path(r"C:\Users\unesh\.gemini\antigravity\brain\9679e9c0-134e-472e-b43a-9b447ab8bd27\playwright_evidence")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def run_e2e_test():
    results = {}
    print("=== Starting Playwright Autonomous E2E Test on HINA ===")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()

        # 1. Navigation & Initial Load
        print("[1/5] Navigating to http://127.0.0.1:5173...")
        start_t = time.time()
        page.goto("http://127.0.0.1:5173", wait_until="domcontentloaded", timeout=15000)
        page.wait_for_timeout(4000)
        nav_duration = round(time.time() - start_t, 2)
        print(f"       Page loaded in {nav_duration}s. Title: '{page.title()}'")
        
        screenshot_1 = OUTPUT_DIR / "step1_initial_workspace.png"
        page.screenshot(path=str(screenshot_1))
        results["step1_initial_workspace"] = str(screenshot_1)

        # Assert Workspace Connection
        body_text = page.inner_text("body")
        has_workspace_connected = "Workspace connected" in body_text or "Connected" in body_text
        print(f"       Backend Connected Indicator: {'PASS' if has_workspace_connected else 'FAIL'}")
        results["backend_connected"] = has_workspace_connected

        # 2. Companion Stage & Subtitle / Waveform Layout Verification
        print("[2/5] Inspecting 3D Companion Stage and Layout Separation...")
        waveform_pill = page.locator(".iris-waveform-stage")
        has_waveform = waveform_pill.count() > 0
        print(f"       Waveform status pill present: {has_waveform}")
        
        sub_card = page.locator("[data-testid='work-companion-panel']").locator("div").filter(has_text="Hey babe!").last
        has_sub_card = sub_card.count() > 0
        print(f"       Subtitle speech card present: {has_sub_card}")

        if has_waveform and has_sub_card:
            box_waveform = waveform_pill.bounding_box()
            box_sub = sub_card.bounding_box()
            if box_waveform and box_sub:
                gap = box_sub["y"] - (box_waveform["y"] + box_waveform["height"])
                is_clean_stack = box_waveform["y"] < box_sub["y"]
                print(f"       Waveform Box: y={round(box_waveform['y'], 1)}, h={round(box_waveform['height'], 1)}")
                print(f"       Subtitle Box: y={round(box_sub['y'], 1)}, h={round(box_sub['height'], 1)}")
                print(f"       Vertical Separation Gap: {round(gap, 1)}px (Clean Stack: {is_clean_stack})")
                results["layout_clean_stack"] = is_clean_stack

        # 3. Live Chat Turn Execution
        print("[3/5] Executing Live Turn with HINA Chat Interface...")
        composer = page.locator("textarea").first
        if composer.count() > 0:
            test_prompt = "Hello Hina! What are your core capabilities?"
            print(f"       Typing prompt: '{test_prompt}'")
            composer.click()
            composer.fill(test_prompt)
            page.wait_for_timeout(500)
            
            # Click submit button or press Enter
            submit_btn = page.locator("button[type='submit'], button[aria-label*='Send'], button[aria-label*='send']").first
            if submit_btn.count() > 0:
                print("       Clicking send button...")
                submit_btn.click()
            else:
                print("       Pressing Enter...")
                composer.press("Enter")
            
            print("       Waiting for Hina's streaming response...")
            page.wait_for_timeout(7000)
            
            screenshot_chat = OUTPUT_DIR / "step4_chat_response.png"
            page.screenshot(path=str(screenshot_chat))
            results["step4_chat_response"] = str(screenshot_chat)
            print("       Captured live conversation screenshot.")

        # 4. Tab Navigation (Dashboard, Models)
        print("[4/5] Testing Navigation Tabs...")
        # Models view
        models_btn = page.locator("button, div[role='button']").filter(has_text="Models").first
        if models_btn.count() > 0:
            models_btn.click()
            page.wait_for_timeout(2000)
            screenshot_models = OUTPUT_DIR / "step3_models_view.png"
            page.screenshot(path=str(screenshot_models))
            results["step3_models_view"] = str(screenshot_models)
            print("       Navigated to Models library successfully.")

        # Return to Chat
        chat_btn = page.locator("button, div[role='button']").filter(has_text="Chat").first
        if chat_btn.count() > 0:
            chat_btn.click()
            page.wait_for_timeout(1500)
            print("       Returned to Chat canvas.")

        # 5. Final State Screenshot
        print("[5/5] Finalizing Test Report...")
        final_screenshot = OUTPUT_DIR / "step5_final_state.png"
        page.screenshot(path=str(final_screenshot))
        results["step5_final_state"] = str(final_screenshot)

        browser.close()

    print("\n=== Playwright Autonomous Test Complete ===")
    for k, v in results.items():
        print(f" - {k}: {v}")
    return results

if __name__ == "__main__":
    run_e2e_test()

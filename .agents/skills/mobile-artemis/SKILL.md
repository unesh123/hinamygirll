---
name: mobile-artemis
description: Autonomous Android and mobile device automation framework by Google. Control physical Android devices and emulators with natural language, inspect screens, run high-speed tasks, and verify UI states.
---

# mobile-artemis

Google ARTEMIS is an end-to-end autonomous mobile control framework. It translates high-level natural language instructions into precise Android actions (ADB, UI Automator, touch gestures, key events, and visual verification).

## When to Use This Skill
- The user asks to control, test, or interact with an Android phone or emulator.
- Automated app workflows: launching apps, filling forms, navigating multi-step screens, verifying outputs.
- Diagnosing device state, inspecting active packages, capturing device screenshots, and capturing logs.

## Core Architectural Modes
1. **ARTEMIS Flash (Fast / Reactive Mode)**:
   - For rapid, lightweight UI operations and direct tasks.
   - Operates in a tight Observe-Think-Act loop with single LLM inference.
   - Chains consecutive taps into fast bursts to catch transient UI (toasts, fading controls).
2. **ARTEMIS Pro (Deep Graph / Multi-Agent Closed-Loop Mode)**:
   - For multi-branch workflows, error-recovery loops, and long multi-screen tasks.
   - Uses Planner -> Operator -> Checker verification at critical checkpoints.

## Dynamic-First, Coordinate-Fallback Philosophy
1. **Dynamic Locating**: Always search by Accessibility Label, Resource ID, or OCR Text first. This makes the interaction resilient across screen resolutions and device densities.
2. **Coordinate Fallback**: If the dynamic locator fails, fall back to precise touch coordinates `(X, Y)` verified on the live screenshot.

## Common Device Actions
- **Launch Application**: `adb shell monkey -p <package> -c android.intent.category.LAUNCHER 1`
- **Tap Screen**: `adb shell input tap <X> <Y>`
- **Swipe / Scroll**: `adb shell input swipe <X1> <Y1> <X2> <Y2> <duration_ms>`
- **Type Text**: `adb shell input text '<escaped_text>'`
- **Key Event**: `adb shell input keyevent <KEYCODE>` (3 = Home, 4 = Back, 66 = Enter, 187 = AppSwitch)
- **Screenshot Capture**: `adb exec-out screencap -p > screenshot.png`

## Integrated Tools in HINA
- `mobile_run_task`: Execute natural-language mobile tasks on connected devices.
- `mobile_get_device_state`: Get live screenshot, connected devices, active foreground package, and battery.
- `mobile_tap_screen`: Tap specific screen coordinates or UI elements.
- `mobile_type_text`: Type text into the focused Android input field.
- `mobile_key_press`: Send hardware keys (Home, Back, Recents, Power).
- `mobile_diagnose`: Verify ADB installation and device connection health.

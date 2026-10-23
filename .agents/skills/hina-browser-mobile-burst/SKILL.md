---
name: hina-browser-mobile-burst
description: High-speed Playwright CDP and Google ARTEMIS action-burst automation with pre-execution accessibility tree validation
---

# High-Speed Browser & Mobile Action-Burst Protocol

## 1. Zero Turn-Wait Action Bursts
Traditional agents take a screenshot, wait 3 seconds, click once, and repeat. HINA executes multi-action bursts in a single cycle:
- Extract compact interactive accessibility tree via Chrome DevTools Protocol (`page.accessibility.snapshot()`) or Android accessibility node hierarchy.
- Validate pre-conditions locally without round-tripping 2MB base64 images.
- Execute batched arrays of actions in one atomic execution step.

## 2. Action Burst Schema
```json
{
  "burst_intent": "Authenticate and navigate to the project dashboard in one step",
  "pre_check_selector": "input#email",
  "actions": [
    { "type": "fill", "target": "input#email", "value": "hina@intelligence.os" },
    { "type": "fill", "target": "input#password", "value": "secret_token" },
    { "type": "click", "target": "button[type='submit']" },
    { "type": "waitForUrl", "value": "/dashboard" }
  ],
  "post_verification": "div[data-testid='dashboard-ready']"
}
```

## 3. Google ARTEMIS Mobile Automation Integration
- Connect to `adb` server socket (`tcp:localhost:5037`).
- Map Android accessibility nodes to numbered bounding boxes.
- Compress interaction history into compact semantic text to preserve context window capacity.

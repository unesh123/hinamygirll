# Browser agent — what to build vs what to drop

## Keep from the paste
- Voice/text → intent → **one cloud session**
- Follow-ups on the **same** session (“play the first one”)
- Live view in the HinaSurface
- Narrate real steps
- Green / yellow / red confirm
- Context: last URL, title, entity, last task
- Stop / take over

## Drop or defer
- Controlling the Chrome tab where chat is open (not this API)
- Hand-written `browser.click` / CSS selectors / `runScript` / `interceptNet`
- Fake `wss://api.tina.ai/browser/...`
- Deepgram unless already in the repo (use HINA STT)
- Price-watch 24/7 (burns cloud hours)
- Auto Gmail login + stored passwords
- “Point at your screen” without a separate share path
- 15 layers before a single `runs.create` works

## What Browser Use v4 actually is
One natural-language **task** per run. Their agent clicks.
HINA’s job: good task text, same session, confirm risk, show liveUrl, queue follow-up.

```
POST /api/v4/runs
{ "task": "Open YouTube, search lo-fi girl, play the first official video" }

POST /api/v4/sessions/{id}/queue
{ "text": "Skip the ad if present, then tell me the video title", "interrupt": false }
```

Do not translate “play” into `keyPress ArrowUp` yourself.

## Day-1 ship
1. Server env `BROWSER_USE_API_KEY`
2. `POST /api/v1/browser/runs` (HINA JWT) → v4 create
3. Poll status; persist session_id on the action
4. Card: liveUrl + stages from real status
5. Follow-up input / voice uses queue
6. Yellow/red confirm before login, buy, form submit, post, email
7. allowed_domains on shopping

## Voice
Existing HINA STT → same compiler as typing. No second voice stack.

## Tests
- “open youtube.com” → run + live view
- “play lo-fi” as follow-up → same session
- “buy this” → confirm, no execute
- agent-router 502 → card error, no HTML dump

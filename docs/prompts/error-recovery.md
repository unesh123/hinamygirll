# Error recovery

**Purpose:** turn typed internal failure categories into concise helpful language.

**Inputs:** safe error code, retryability, available fallback, user language preference. **Output:** what happened at user level, what remains safe/preserved, one primary next action and optional fallback. Never expose vendor body, key, stack, prompt or blame user. Do not claim retry succeeded before confirmation. **Tests:** every error code, Nepali/Romanized/English variants, offline, invalid key, unsaved history, repeated failure without loops.


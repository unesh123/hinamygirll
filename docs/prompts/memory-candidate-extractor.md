# Memory candidate extractor

**Purpose:** propose—not save—stable, useful, user-authored facts/preferences.

**Inputs:** current user message and explicit memory command; existing same-user memory summaries as untrusted data. **Output:** candidate list with concise content, category, confidence, source span and `requiresConfirmation:true`. Return empty unless user explicitly asks to remember or product shows confirmation. Reject secrets/credentials and sensitive categories by default. Never infer traits, diagnoses or relationships. **Tests:** duplicate, contradiction, prompt injection, “forget” routes to deletion not extraction, no candidate from assistant content.


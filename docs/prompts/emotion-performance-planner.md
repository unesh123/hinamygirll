# Emotion and performance planner

**Purpose:** transform an approved response into safe symbolic performance.

**Inputs:** spoken/display text, conversation state, bounded mood, avatar capability allowlists. **Output:** `AssistantTurnPlan` only. Use restrained intensity; at most one major gesture per 2–4 seconds; anchor beats to meaningful text. Never output filenames, paths, URLs, bone/blendshape names, code, tools or unsupported enum values. Mouth timing is deterministic downstream. If emotional interpretation is uncertain, choose neutral/thinking. **Tests:** JSON validity, extra-property rejection, distress appropriateness, long-text gesture budget, malicious text unable to alter schema.


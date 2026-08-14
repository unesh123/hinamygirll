# HINAA Text Humanizer Options

## Purpose and boundary

HINAA’s humanizer is a **writing-quality and voice-preservation tool**. It should improve flow, sentence rhythm, clarity, warmth, and audience fit while preserving facts, citations, code, links, quotations, names, numbers, and the user’s language. It must not claim to evade AI detectors, impersonate a specific human author, or conceal academic/professional authorship requirements.

## Current verified implementation

The shipped **Text Humanizer** is a private, deterministic HINAA route at `POST /v1/text/humanize`. It has no provider dependency and returns `externalTextTransfer: false`. Its Studio is available through `@humanize` and the real **Local tools → Humanize a draft** shortcut. The Studio offers **Natural**, **Warm**, **Professional**, and **Concise** modes; copy; editable use-as-draft; a one-step local restore; clear; a responsive mobile-safe layout; visible character counts; a change summary; and a user-triggered **Save to project** action for the currently selected private project.

Before polishing prose, the route leaves Markdown fenced/inline code, Markdown links, URLs, citation markers, email addresses, Windows/Unix paths, headings, lists, tables, quotations, Hindi text, numbers, and other protected spans untouched. It returns the count and total characters of protected spans so the user can see that the safety layer was active. It does not simulate a neural rewrite, evade detectors, or impersonate a person.

| Option | Where the text is processed | Strengths | Trade-offs | HINAA integration status |
|---|---|---|---|---|
| **Local deterministic polish** | Inside HINAA only | Private, instant, no key/network; normalizes spacing and removes narrowly defined filler while reporting protected spans | Intentionally conservative; it does not perform a creative rewrite | **Implemented and default** |
| **Configured HINAA brain** | User-selected Qwen, Claude, CX, or compatible provider | Can provide a higher-variance rewrite when the user explicitly requests one in chat | Text is sent to the selected provider; depends on valid configuration; not exposed as a Humanizer Studio route | **Chat-only alternative; not the private tool** |
| **Local Ollama model** | User’s own local machine at the Ollama API | Fully local model inference and no additional cloud text transfer; chat API accepts message history and generation options [1] | Requires an installed model, RAM/VRAM, and independent availability/quality validation | **Not implemented** |
| **LanguageTool style/grammar pass** | LanguageTool HTTP endpoint | Focused grammar/spelling/style corrections; documented request and rate limits [2] | It is proofreading, not true voice-aware humanization; remote use needs explicit configuration and text leaves the machine | **Not implemented** |

## Optional quality route: configured HINAA brain

Qwen’s platform documents an OpenAI-compatible chat-completions route for creative writing and related language tasks.[3] That makes the already configured HINAA brain a reasonable **explicit chat alternative** for a more creative rewrite. It is deliberately not silently chained behind the local humanizer. A cloud-backed rewrite must display the provider name and state that the selected text will leave the local process before the request is made.

```text
Private Humanizer: local deterministic polish only
Creative rewrite in chat: use the selected HINAA brain and explicitly request fact/citation preservation
```

## Required quality contract

The humanizer prompt and fallback must obey the following contract.

| Preserve exactly | Improve only when appropriate |
|---|---|
| Facts, numbers, dates, names, links, source citations, code blocks, quotes, headings, tables, file paths, explicit language choice | Repetition, robotic transitions, choppy sentence flow, empty filler, overly formal phrasing, excessive passive voice, mismatched audience tone |

The result offers four explicit styles: **Natural**, **Warm**, **Professional**, and **Concise**. HINAA returns the polished text, a small change summary, original/output character counts, and protected-span metrics. The user can copy the result, replace the editable source draft, restore the immediately preceding source locally, or clear the session. After choosing a project in HINAA’s local workspace, the user can explicitly save the result as a `document` artifact. The saved metadata records that the origin was `local-humanizer`, the selected style, the local route, `externalTextTransfer: false`, character counts, and protected-span count; no cloud transfer or external publication occurs.

## References

[1]: https://docs.ollama.com/api/chat "Ollama Chat API"
[2]: https://languagetool.org/http-api/ "LanguageTool HTTP API"
[3]: https://qwen.ai/apiplatform "Qwen API Platform"

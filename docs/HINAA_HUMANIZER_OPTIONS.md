# HINAA Text Humanizer Options

## Purpose and boundary

HINAA’s humanizer is a **writing-quality and voice-preservation tool**. It should improve flow, sentence rhythm, clarity, warmth, and audience fit while preserving facts, citations, code, links, quotations, names, numbers, and the user’s language. It must not claim to evade AI detectors, impersonate a specific human author, or conceal academic/professional authorship requirements.

## Recommended implementation order

| Option | Where the text is processed | Strengths | Trade-offs | HINAA integration decision |
|---|---|---|---|---|
| **Local deterministic polish** | Inside HINAA only | Private, instant, no key or network; removes repeated fillers, fixes whitespace, preserves code/URLs/Markdown, and applies an audience-oriented rewrite brief | Cannot create high-quality stylistic rewriting without a language model | **Default fallback** |
| **Configured HINAA brain** | User-selected Qwen, Claude, CX, or compatible provider | Best prose quality; uses HINAA’s existing selected-provider and diagnostic/approval paths; can preserve Hindi × English style | Text is sent to the selected model provider; depends on a valid key and available model | **Primary quality route** |
| **Local Ollama model** | User’s own local machine at the Ollama API | Fully local model inference and no additional cloud text transfer; chat API accepts message history and generation options [1] | Requires an installed model, RAM/VRAM, and quality depends on the local model | **Optional private quality route** |
| **LanguageTool style/grammar pass** | LanguageTool HTTP endpoint | Focused grammar/spelling/style corrections; documented request and rate limits [2] | It is proofreading, not true voice-aware humanization; remote use needs explicit configuration and text leaves the machine | **Optional proofreading companion, not default** |

## Why Qwen is the first quality option for this installation

The user has already configured Qwen for HINAA. Qwen’s API platform describes its OpenAI-compatible chat-completions route for conversion, creative writing, translation, summarization, coding, and other text tasks. [3] Therefore, HINAA can make Qwen humanization available through the existing Qwen provider rather than adding a second unknown “humanizer” service and another key.

HINAA must display the selected route before execution:

```text
Humanize with: Local polish | Current HINAA brain | Local Ollama (when configured)
```

When the selected brain is cloud-hosted, the UI must state that the requested text will be sent to that provider. When Local polish is selected, no text leaves the HINAA process.

## Required quality contract

The humanizer prompt and fallback must obey the following contract.

| Preserve exactly | Improve only when appropriate |
|---|---|
| Facts, numbers, dates, names, links, source citations, code blocks, quotes, headings, tables, file paths, explicit language choice | Repetition, robotic transitions, choppy sentence flow, empty filler, overly formal phrasing, excessive passive voice, mismatched audience tone |

The result should offer four explicit styles: **Natural**, **Warm**, **Professional**, and **Concise**. HINAA should return the rewritten text plus a small change summary. The user must be able to copy the result, replace the source draft, or save it as a local project artifact.

## References

[1]: https://docs.ollama.com/api/chat "Ollama Chat API"
[2]: https://languagetool.org/http-api/ "LanguageTool HTTP API"
[3]: https://qwen.ai/apiplatform "Qwen API Platform"

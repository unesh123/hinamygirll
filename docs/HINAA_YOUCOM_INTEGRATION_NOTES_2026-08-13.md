# You.com Platform Integration Notes — 2026-08-13

## Verified capability surface

You.com exposes five relevant APIs for HINAA: Web Search, Answer, Contents, Research, and Finance Research. The canonical environment variable is `YDC_API_KEY`; requests use the `X-API-Key` header. HINAA should treat this service as a **grounded retrieval/research provider**, not as a replacement for the configured CX conversation brain.[1]

| HINAA mode | Verified You.com operation | User-visible result | Integration policy |
|---|---|---|---|
| Fast lookup | `POST https://api.you.com/v1/search` | Structured current web/news results, snippets or query-aware highlights, URL/title metadata. | Default current-web retrieval path. Return attributed source cards. |
| Cited answer | `POST https://api.you.com/v1/answer` | One synthesized answer with verified inline citations and source excerpts. | Use for explicit factual questions needing a concise cited answer. |
| Read selected URLs | `POST https://ydc-index.io/v1/contents` | Clean Markdown/HTML and optional metadata for supplied URLs. | Use after the user explicitly asks to read/compare selected pages, or as an approved agent substep. |
| Deep research | `POST https://api.you.com/v1/research` | Multi-step Markdown synthesis with `[[n]]` citations and source list; effort levels from `lite` through `frontier`. | Keep fast `lite`/`standard` user-approved. Reserve deep, exhaustive, and background tasks for explicit approval and visible progress. |
| Finance research | `POST https://api.you.com/v1/finance_research` | Cited financial research based on a finance-optimized index. | Optional, explicit-confirmation-only, labeled as research rather than personalized investment advice. |

## Cost and latency controls

Search should default to five results with `extraction_mode: highlights`, avoiding full-page extraction unless the user asks to read pages. Research defaults to `lite`; it should never silently select `deep`, `exhaustive`, or `frontier`. Finance research is not part of ordinary chat and requires an explicit tool approval. These policies protect the user’s prepaid credits while retaining real-time grounding.[2] [3]

## Local configuration finding

The checked sandbox project has no local `.env.local` file and no recognized You.com variable. HINAA’s backend loads `apps/api/.env.local`; therefore a Windows-local key does not appear in this sandbox. The integration will support `YDC_API_KEY` without persisting it to Git. Runtime key validation must be performed only on the user’s local HINAA runtime after restart.

## References

[1]: https://you.com/docs/quickstart "You.com API Quickstart"
[2]: https://you.com/docs/guides/search "You.com Web Search API Overview"
[3]: https://you.com/docs/guides/research "You.com Research API Overview"
[4]: https://you.com/docs/api-reference/answer/v1-answer "You.com Answer API Reference"
[5]: https://you.com/docs/api-reference/contents "You.com Contents API Reference"
[6]: https://you.com/docs/api-reference/finance-research/v1-finance_research "You.com Finance Research API Reference"


## Chosen HINAA capability contract

HINAA will retain CX as the conversation brain and use You.com only when fresh external evidence is required. Existing explicit tool confirmation remains mandatory before a paid web request is sent. The deterministic command router will propose **Web search** for fast lookup language, **Cited answer** for answer-with-sources language, **Deep research** only for explicit research/compare/investigate language, and **Read pages** only when specific URLs are supplied. No generic chat message silently triggers paid browsing.

The implementation will expose a single `YouComClient` with typed public methods and a normalized source record. It will never return the API key, raw headers, or an unbounded response body. Normalized source data will include a stable display identifier, title, canonical URL, and bounded evidence snippet. The configured provider is tried first for `web_search`; legacy DuckDuckGo parsing remains only as a transparent no-key fallback. Explicit answer/research/content/finance tools do not silently fall back because their cited output contract differs.

| Tool | Confirmation | Default limit | Failure behavior |
|---|---:|---:|---|
| `web_search` | Required | Five sources; highlight extraction | Surface whether You.com is unconfigured, rejected, rate-limited, or unavailable; use legacy public search only when no You.com key is configured. |
| `web_answer` | Required | One cited response | Return answer plus citations, never a fabricated source list. |
| `web_research` | Required | `lite` effort | Only requested effort is sent; expensive levels remain visible in the approval parameters. |
| `web_extract` | Required | Five requested URLs | Validate HTTP/HTTPS URLs and return bounded Markdown previews with source metadata. |
| `finance_research` | Required, high sensitivity | `deep` effort | Return cited informational research; HINAA must not frame it as personalized trade or investment execution advice. |


## Image-search capability boundary

You.com documents `GET https://api.you.com/v1/images?q=...` as an image URL search endpoint, but explicitly labels it **beta and unmaintained** and says access is limited to early-access partners. HINAA may expose it as an explicit, confirmation-gated preview tool that returns public image and source-page URLs when the configured key has access. A `403` must be presented as an access limitation with an actionable request path, not as an image-search failure or generated-image capability.[7]

[7]: https://you.com/docs/api-reference/images/images "You.com Images API Reference"

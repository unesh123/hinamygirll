# ADR-011: Azure Speech plus Gemini as candidate route

## Status
Proposed pending Phase 2 benchmark — checked 2026-07-30

## Context and purpose
Owner has Azure student credit; primary users need Nepali; Gemini official API is available in Nepal.

## Decision
Benchmark Azure Speech `ne-NP` with Hemkala/Sagar and configured Gemini `gemini-3.6-flash`; evaluate `gemini-3.5-flash-lite` for background jobs. These are configuration defaults only after portal/capability and sealed-dataset evidence.

## Alternatives considered
Azure model/Foundry, another official realtime provider, modular alternative and local Ollama-compatible model remain benchmark candidates.

## Reasoning
Official catalogs confirm current availability, but accuracy/quota/latency/cost are deployment-specific.

## Risks and consequences
Catalog IDs, tiers, data terms and quotas change; free-tier data use is unsuitable for sensitive content.

## Acceptance criteria / revisit
Accept only after benchmark and budget/privacy review. Recheck official model, region, terms and pricing at implementation and demo dates.


# ADR-003: Provider ports and hybrid voice

## Status
Accepted — 2026-07-30

## Context and purpose
Nepali quality, latency, privacy, quotas and catalogs differ by vendor.

## Decision
Vendor-neutral ports plus Path A provider-direct speech-to-speech and Path B STT→LLM→TTS cascade. Cascade is baseline; selection is benchmark-driven.

## Alternatives considered
One vendor end-to-end is simpler but creates lock-in and may underperform Nepali. Fully local inference exceeds likely device/server budget.

## Reasoning
Ports support official providers, mock/local adapters and transparent fallback.

## Risks and consequences
Lowest-common-denominator contracts and more tests. Capability negotiation keeps optional features explicit.

## Acceptance criteria / revisit
Mock and two candidate adapters pass one contract suite. Revisit interfaces when two real adapters expose an unmodelled common capability.


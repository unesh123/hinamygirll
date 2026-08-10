# Agent Router Architecture

The Agent Router implementation in HINAA securely tunnels requests through an external provider while strictly maintaining the HINAA architectural contracts (PromptPackage, AssistantTurnPlan, and streaming constraints).

## Overview

1. **Provider Layer (`AgentRouterProvider`)**
   - Implements `LLMProvider`.
   - Distinct from `OpenAILLMProvider` to ensure strict parameter control.
   - Prevents blind passthrough of undocumented or unverified features.

2. **Security & Configuration**
   - Configured exclusively via `.env.local` (`AGENT_ROUTER_API_KEY`, `AGENT_ROUTER_BASE_URL`).
   - The frontend CANNOT override the base URL or API key. This prevents SSRF (Server-Side Request Forgery).

3. **Model Allowlisting**
   - The backend validates requested models against `AGENT_ROUTER_ALLOWED_MODELS`.
   - Unverified or unapproved models are rejected at the `ProviderRouter` layer.

4. **Integration with HINAA**
   - The `stream_plan` method forces responses into the `AssistantTurnPlan` format.
   - Any failure in the Agent Router (e.g., timeouts, JSON errors) maps securely to a safe `HinaaError`, ensuring the frontend degrades gracefully to mock or fallback states.

# Gateway URL Security Rules

To prevent Server-Side Request Forgery (SSRF) and credential leakage, HINAA enforces strict isolation between providers and their configurations.

## The SSRF Threat
If the frontend were allowed to pass an arbitrary `gatewayUrl` to the backend and the backend used it to instantiate a provider:
1. An attacker (or compromised frontend) could provide a malicious URL (e.g., `https://attacker.com`).
2. The backend would blindly attach high-value API keys (like `AGENT_ROUTER_API_KEY`) to the request.
3. The API key would be leaked to the attacker.
4. The frontend could also probe internal networks (e.g., `http://127.0.0.1:8080`) bypassing firewalls.

## Remediation Rules Implemented
1. **No URL Passing in TurnRequests**: `TurnRequest` and `ConversationRequest` do NOT accept `customBaseUrl` or `agentRouterBaseUrl`.
2. **Server-Owned Origins**: The backend resolves the base URL and API key entirely from `.env.local`.
3. **Provider Isolation**:
   - `OPENAI_CODEX_API_KEY` is ONLY sent to `OPENAI_CODEX_BASE_URL` (Custom Gateway).
   - `AGENT_ROUTER_API_KEY` is ONLY sent to `AGENT_ROUTER_BASE_URL`.
   - Never cross-pollinate credentials.
4. **Development Tunnels**: If a developer updates their `trycloudflare` tunnel, they must update `.env.local` and restart the backend. This guarantees the origin is approved by the server owner.

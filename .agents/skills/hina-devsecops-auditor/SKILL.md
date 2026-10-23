---
name: hina-devsecops-auditor
description: Production DevSecOps & Distributed Systems Resilience Auditor based on the 111 Engineering Checklist
---

# Production DevSecOps & Resilience Audit Protocol

## 1. Scope & Defensive Mission
- Audits user-owned codebases, APIs, and cloud deployments against the 111 Production Engineering Checklist.
- Purely defensive: identifies vulnerabilities, secret exposures, and architectural bottlenecks, producing automated pull requests and remediation patches.

## 2. Core Audit Vectors (#67–#80)
1. **#67 Secret Leak Detection**: Regex scanning for API keys (Stripe, OpenAI, ElevenLabs, Azure, AWS) in git commit histories and static bundles.
2. **#68 & #70 IAM and JWT Security**: Validate least-privilege token scopes, RS256 signing, short TTLs (<15m), and automatic refresh token rotation.
3. **#76 CORS Misconfiguration**: Enforce explicit origin allowlists; reject wildcard `Access-Control-Allow-Origin: *` with credentials.
4. **#77 CSRF Protection**: Verify `SameSite=Lax/Strict` cookies and double-submit anti-CSRF tokens.
5. **#78 SQL Injection**: Verify parameterized queries with ORM/pgvector; block raw SQL string interpolation.
6. **#79 Cross-Site Scripting (XSS)**: Verify DOM sanitization, CSP headers (`Content-Security-Policy`), and React escaping.
7. **#80 Server-Side Request Forgery (SSRF)**: Validate egress URL IP addresses against RFC 1918 private subnets and cloud metadata IPs (`169.254.169.254`).

## 3. Distributed Systems Resilience (#1–#14)
- **#1 Token-Bucket Rate Limiting**: Prevent upstream API exhaustion.
- **#10 Circuit Breakers**: Fast-fail unresponsive backends with half-open recovery probes.
- **#12 & #13 Retries with Exponential Backoff + Jitter**: Prevent thundering herd problems.
- **#56 & #57 Health & Readiness Probes**: Continuous liveness heartbeats on `/api/health`.

# Security Threat Model & Defense Architecture

## 1. System Threat Landscape

The HNA / HINA platform operates across multi-modal interfaces, persistent conversational memory, tool execution runtimes, and external LLM APIs. This document details the threat boundaries, attack vectors, and implemented countermeasures.

---

## 2. Authentication, Sessions & Tenant Isolation

### 2.1 Identity & Session Management
- **Identity Provider**: Clerk handles authentication, session lifecycles, and multi-factor authentication.
- **JWT Verification**: The backend (`apps/api/hinaa_api/auth.py`) cryptographically verifies Bearer JWT tokens on every protected endpoint.
- **Session Expiry**: Sessions are strictly bounded with rolling token expiration. Inactive tokens are revoked immediately.

### 2.2 Tenant & Cross-User Isolation
- **Boundary**: All user conversations, memory fragments, uploaded files, and agent logs are tagged with `user_id`.
- **Query Hardening**: Every SQL/ORM query enforces `WHERE user_id = :current_user_id`.
- **Cross-User Leakage**: Prevented at the database query layer. An authenticated user attempting to query another user's `conversation_id` receives HTTP 404.

---

## 3. Tool Sandboxing & Computer Operator Execution

### 3.1 Cloud vs. Local Separation
A cloud server must never directly operate an arbitrary user device.
- Cloud instances on Render execute within locked container environments.
- Local desktop automation (`computer_operator.py`) requires an explicitly paired local companion agent running on the user's host machine.

### 3.2 Command Injection & Path Traversal Guards
- **Restricted Directories**: Desktop tool execution is strictly confined to a configured workspace directory (`CWD`).
- **Path Canonicalization**: File operations resolve symlinks and canonicalize paths (`os.path.realpath`) to block directory traversal (`../..`).
- **Forbidden Binaries**: Execution of destructive commands (`rm -rf /`, `del /f /s /q C:\`, formatting drives, registry alterations) is unconditionally blocked by policy.

### 3.3 High-Impact Approval Contract
For any action classified as high-impact (file deletion, network modification, shell script execution):
- **Approval Scope**: Single-use token bound to `{actor_id, exact_action, target_resource, expiry_timestamp}`.
- **No Self-Approval**: The LLM cannot approve its own actions or expand its authorization boundaries. Execution requires explicit confirmation in the UI.

---

## 4. Prompt Injection & Content Sanitization

| Attack Vector | Threat Description | Defense Mechanism |
| :--- | :--- | :--- |
| **Indirect Prompt Injection** | Untrusted web search results, PDFs, or external tool responses contain adversarial instructions to hijack the agent. | External content is treated as untrusted data; ingested within isolated XML delimiter tags (`<untrusted_content>`) and stripped of control tokens. |
| **Direct Jailbreak** | User attempts to override core system directives and behavioral constraints. | System prompt is anchored in system message role; execution policies and safety rules are enforced in application code outside model text. |
| **Unsafe UI Rendering (XSS)** | Model generates malicious HTML or JavaScript embedded in markdown output. | Markdown parser strictly sanitizes HTML tags; script tags and raw iframe elements are disallowed. |

---

## 5. Secret Storage & Operational Redaction

- **Zero Secret Ingestion**: Environment variables containing API keys (`GEMINI_API_KEY`, `CLERK_SECRET_KEY`, etc.) are never logged, persisted in chat history, or returned in client payloads.
- **Log Scrubber**: A logging filter intercepts all outgoing log streams and masks sensitive patterns (Bearer tokens, API keys, email addresses, authorization headers).
- **CORS Policy**: Configured to accept requests only from authorized origins (production domain and approved development localhost).

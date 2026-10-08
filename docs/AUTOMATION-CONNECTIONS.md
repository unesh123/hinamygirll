# Hina connections and remaining work — 6 October 2026

## Current facts

The web workspace is deployed at https://hinaa-workspace.vercel.app. Its API still runs on your Windows PC through a supervised temporary Cloudflare tunnel. This requires the PC to remain awake and online. A Vercel frontend does not give the agent a Windows desktop or a Linux machine.

PowerShell and installed kali-linux both passed real command execution checks in this review. The public site requires a short-lived owner-bound PC grant before executing host tools. Pairing is created only from the local workspace, checked against the configured owner, and revoked or expired after 15 minutes. Real physical-PC operation through the live browser remains unverified.

The new desktop daemon implements mouse/keyboard/window actions, but this is not a verified autonomous desktop agent. It now requires private pairing, rejects browser-origin requests, and limits payloads. Desktop screenshots and pairing material are excluded from Git. The API and daemon share `.runtime/desktop/bridge.token`; run them as the same Windows user. Existing running daemons must be restarted to pick up the new protocol. Do not expose port 8765 to the internet. Actual end-to-end desktop automation remains unverified.

Editor launch supports `my editor`, `preferred editor`, and `code editor`. Set `HINAA_PREFERRED_EDITOR` to an installed application alias (default Antigravity). Launch errors no longer count as verified success. A complete website workflow still needs an observation/verification loop, bounded command execution, build/test results, and a preview URL. Opening an editor does not prove the website exists.

## Connect your school Outlook

Implemented: delegated Graph token refresh, inbox list/read, real mailbox drafts, and sending acceptance status. No emails were sent during this repair. Default email composition produces a local draft if Outlook is disconnected. A Microsoft HTTP 202 means accepted for processing, not proven delivery.

1. Register a Microsoft Entra application for the school account type. Obtain its Application (client) ID and Directory (tenant) ID. Your school may restrict app registration or consent; ask its administrator if blocked.
2. Enable public client/device-code authentication. Use delegated `User.Read`, `Mail.ReadWrite`, and `offline_access`. `Mail.ReadWrite` permits both inbox reading and saved drafts. Add delegated `Mail.Send` only when sending is needed. This public-client flow does not need a client secret or your mailbox password.
3. From the project root, run:

   ```powershell
   & ./apps/api/.venv/Scripts/python.exe ./scripts/connect-outlook.py --client-id YOUR_APPLICATION_ID --tenant YOUR_TENANT_ID
   ```

   Complete the Microsoft sign-in shown by the script using your own school account. Tokens are encrypted with Windows DPAPI for the current Windows user, written atomically under ignored `.runtime/outlook/`, and never printed. Reconnect if consent is revoked. For sending, reconnect with `--allow-send` after granting `Mail.Send`.
4. In Hina's Integrations panel choose **Read Outlook inbox**, then create a draft. Real-account inbox/draft tests require this sign-in and have not yet been performed. Mail content is untrusted data and must not authorize tools or external disclosure.

The available Codex Outlook Email plugin is a separate optional connection for this assistant. Installing it does not connect Hina's backend mailbox.

Sources: [Microsoft device flow](https://learn.microsoft.com/en-us/entra/identity-platform/v2-oauth2-device-code), [delegated permissions](https://learn.microsoft.com/en-us/graph/permissions-reference), [create draft](https://learn.microsoft.com/en-us/graph/api/user-post-messages?view=graph-rest-1.0), [sending acceptance](https://learn.microsoft.com/en-us/graph/api/user-sendmail?view=graph-rest-1.0).

## Credentials and services still needed

| Capability | What to provide or run | Remaining integration work |
|---|---|---|
| School Outlook | Microsoft app client ID, tenant ID, delegated user consent | Run the connector and verify inbox + saved draft; administrator consent if school policy requires it |
| GitHub API | Repository-scoped GitHub token via `GITHUB_TOKEN`, or GitHub App installation | Check permissions with the intended repository; API tooling is not Git MCP |
| GitHub MCP | Repository-scoped backend `GITHUB_TOKEN` | Official remote read-only transport, JSON/SSE responses, discovery, bounded requests, cleanup and agent tool implemented; real authenticated discovery still needs credentials |
| Social media | A developer application/OAuth grant for each selected platform and account | Implement platform-specific adapters, refresh, webhooks/rate limits, and review-before-send/publish; no universal social-media key exists |
| ElevenLabs | Valid configured account/key, available quota, selected voice and language-compatible model | Already has progressive phrase playback; provider/device latency and lip-sync acceptance still need live browser checks |
| Image generation | Configured provider with working entitlement/credits, or reachable local ComfyUI | Earlier provider checks found billing/account/connectivity failures; a key alone does not guarantee image generation |
| PDF/documents | Existing local renderers/parsers and a supported output template | No separate PDF key needed for local creation; verify actual exported artifacts rather than completed-looking cards |
| Windows control | Interactive Windows session + private desktop daemon + owner PC grant | HTTP/voice session grants implemented and tested; actual desktop actuation and task cancellation/recovery still require real acceptance |
| Linux jobs | Installed WSL/Kali for local work, or provisioned Linux container/VPS | Local Kali verified; cloud terminal and independent persistent hosting remain pending |
| 24/7 cloud API | Persistent hosting, HTTPS origin, production Clerk owner auth and volumes | Cloud packaging exists; actual container host/deployment has not been verified |

Store secrets server-side in ignored environment files or a secret manager. Keep them out of frontend `VITE_*` variables and chat. On a cloud host, Windows DPAPI cache files are not portable; implement a host secret-store-backed delegated credential vault rather than copying local credentials. `OUTLOOK_ACCESS_TOKEN` is supported for a temporary managed-token integration, but an expiring access token alone is not an ongoing connection.

GitHub MCP source: [official server and authentication](https://github.com/github/github-mcp-server). Each social platform needs its own chosen account, supported operations, OAuth scopes and published API adapter before Hina can claim it works. Selecting those services comes before registering their credentials.

## Acceptance still required

Real school-account consent/inbox/draft; editor window verification; a complete create-website/build/preview task; physical-PC cancellation/recovery tests; social-account adapter tests; independent cloud runtime; authenticated desktop/mobile browser checks including measured audio latency and GPU frame performance. These are outstanding capabilities, not finished claims.


## Pair a PC session

In the **local workspace** terminal drawer, expand **PC connection** and create a private pairing code. Paste it into **PC connection** in the signed-in live workspace. The code is bound to the configured owner, stored only for that browser tab, never sent to non-Hina URLs, and expires after 15 minutes. Pairing again invalidates the old grant; disconnecting revokes subsequent host actions. Already-running processes require separate cancellation. API restart invalidates all PC grants. Sending email and publishing externally do not become authorized by this PC grant.

The existing desktop daemon must run in your interactive Windows session for physical mouse/window control. This pairing path currently reaches the machine hosting the API. If the API moves to an independent cloud VM, these grants reach that VM's tools; your Windows PC needs a separate outbound device relay before the cloud can control it. The cloud migration has not been performed, and no remote Windows action was executed as part of verification.

## GitHub MCP

The server-side endpoint is GitHub's official `https://api.githubcopilot.com/mcp/readonly`. Configure `GITHUB_TOKEN` in the backend environment/secret store and restart the API. Use **Verify GitHub MCP** in Integrations to validate initialization and tool discovery. The agent-facing `github_mcp` tool can discover schemas and invoke discovered tools annotated read-only. Write operations are not exposed by this connector. Real authentication has not been verified. The Brave GitHub account is signed in, but generating a new repository-scoped credential requires the owner to complete GitHub Confirm access (passkey/authenticator). No backend GitHub token or CLI credential is available yet.

Source: [official remote endpoint and read-only mode](https://github.com/github/github-mcp-server/blob/main/docs/remote-server.md).

## Device timing diagnostics

Settings → Diagnostics now shows avatar render-loop FPS and p95 frame interval, first voice playback onset from submitting text, and provider-reported synthesis duration. Samples are device-local and contain no prompts, audio, credentials or account data. Inactive rendering and absent playback display **Not measured**. These measurements do not substitute for listening, visual lip-sync inspection, mobile layout checks or successful live browser acceptance. The browser tool still rejects the live site due to a saved site permission; no alternate browser/HTTP/desktop-control workaround was used.

## Cloud packaging status

`compose.tls.yaml` and `infra/Caddyfile` add a persistent HTTPS edge for a real Linux host. Compose validation and production configuration checks passed. Docker Desktop acknowledged a startup request, but its Linux engine remained unavailable; image build and runtime checks are unverified. Cloud host credentials, server/project selection, DNS and production Clerk configuration are still required. No resources were provisioned and no server charges were incurred by this repair.

# HINAA OS — Phase 13 Permissions, Grants & Integer Paisa Budgets
## Financial Guardrails, Tier Definitions & Resource Allocations

---

### 1. Integer Paisa Minor-Unit Accounting

All financial operations in HINAA OS utilize **integer paisa** (minor currency units) to eliminate floating-point rounding errors and precision loss:

$$1\text{ NPR} = 100\text{ Paisa}$$

**Conversion Examples:**
- `रु 1.00` = `100 paisa`
- `रु 25.50` = `2,550 paisa`
- `रु 2,500.00` = `250,000 paisa` (default tenant ceiling)

**Tracking Separation:**
- `actual_provider_paisa`: Real paid egress incurred through live cloud LLM APIs.
- `estimated_synthetic_paisa`: Sandboxed local agent simulations.
- `used_paisa`: Combined minor-unit spend.

---

### 2. Autonomous Permission Tiers

| Tier | Name | Allowed Tools | Network Access | Human Approval Required |
|:---|:---|:---|:---:|:---:|
| **Tier A** | Read-Only | `sandbox_read`, `inspect_diff`, `crag_search`, `query_knowledge_graph` | Read-only | No (Autonomous) |
| **Tier B** | Scoped Development | `sandbox_write`, `apply_diff_patch`, `run_sandbox_command`, `browser_navigate` | Whitelisted Domains | No (Autonomous within sandbox) |
| **Tier C** | High-Impact Critical | `simulate_nepali_payment`, `publish_post`, `delete_database`, `deploy_production` | Guarded | **YES** (Mandatory HMAC-signed approval) |

---

### 3. Concurrency & Hardware Resource Limits

```
┌─────────────────────────────────┬────────────────────┬──────────────────────────────────────┐
│ Resource                        │ Default Limit      │ Governor Action on Exhaustion        │
├─────────────────────────────────┼────────────────────┼──────────────────────────────────────┤
│ Max Concurrent Jobs per Tenant  │ 5 jobs             │ Queue hold; rejected with bounded msg│
│ Token Ceiling per Tenant        │ 1,000,000 tokens   │ Job creation paused; alert emitted   │
│ Paisa Ceiling per Tenant        │ 250,000 paisa      │ Job rejected until budget increased  │
│ GPU VRAM Ceiling                │ 16,384 MB (16 GB)  │ Admission denied; prevents OOM panic │
│ Max Concurrent Playwright Browsers 3 instances       │ Worker sleeps until slot released    │
│ Max Concurrent Sandboxes        │ 5 sandboxes        │ Fair-share queue backpressure        │
└─────────────────────────────────┴────────────────────┴──────────────────────────────────────┘
```

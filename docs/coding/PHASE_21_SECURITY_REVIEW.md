# HINAA OS — Phase 21 Security & Host Boundary Review

## 1. Physical Host Environment Disclosure
- **Host OS:** Windows 11 Enterprise (Local Pair-Programming Environment)
- **Reported Capability Bound:** `LOCAL_SANDBOX_RESTRICTED`
- **Container Isolation Reality:** `is_vm_container_isolated: False` (Native Windows; no nested Hyper-V or Linux containers).
- **Execution Policy:** Arbitrary untrusted binary compilation or execution is strictly **blocked**.

---

## 2. Preview Sandbox & Iframe Boundaries

1. **Disallowed Attribute Combination:**
   The combination of `allow-same-origin` and `allow-scripts` is rejected to prevent guest iframe scripts from accessing parent host `localStorage`, cookies, or DOM.
2. **CSP Header Enforcement:**
   All preview responses include:
   ```http
   Content-Security-Policy: default-src 'self' 'unsafe-inline' https: data:; frame-ancestors 'self';
   ```
3. **Workspace Path Traversal Protection:**
   All file read/write operations pass through `_resolve_safe_path()`. Attempts to reference `../`, parent drives, or system folders raise immediate `PermissionError`.

---

## 3. SQLite Transactional Integrity

- All schemas enforce `PRAGMA foreign_keys = ON;`.
- Critical tables use strict atomic constraints (e.g. `CONSTRAINT uq_aircraft_slot UNIQUE (aircraft_id, departure_time)`).
- SQL migrations for midway requirement changes are validated before execution on live databases.

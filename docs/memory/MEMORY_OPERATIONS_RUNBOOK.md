# HINAA OS — Phase 10 Memory Operations Runbook

## 1. Daily & Automated Operations

### 1.1 Health & Diagnostics Probe
Check the status of the SQLite database and memory subsystem:
```bash
curl -s http://127.0.0.1:8000/api/memory/health
```
Expected response:
```json
{
  "status": "healthy",
  "stats": {
    "total_memories": 42,
    "active_memories": 40,
    "contradicted_memories": 2,
    "total_nodes": 18,
    "total_edges": 24,
    "pending_candidates": 3,
    "db_size_bytes": 139264,
    "db_path": "apps/api/data/hinaa_memory.db"
  }
}
```

### 1.2 TTL Expiration Maintenance
Run routine sweep of expired memories via Python:
```python
from hinaa_api.memory import MemoryService
service = MemoryService()
purged_count = service.run_ttl_purge()
print(f"Purged {purged_count} expired memories.")
```

---

## 2. Backup & Disaster Recovery

### 2.1 SQLite Hot Backup
Because the repository operates with Write-Ahead Logging (`WAL` mode), backups can be taken safely without pausing the application:
```bash
sqlite3 apps/api/data/hinaa_memory.db ".backup 'apps/api/data/hinaa_memory_backup.db'"
```

### 2.2 Integrity Check
Verify SQLite B-tree and FTS5 table integrity:
```bash
sqlite3 apps/api/data/hinaa_memory.db "PRAGMA integrity_check;"
sqlite3 apps/api/data/hinaa_memory.db "INSERT INTO memory_fts(memory_fts) VALUES('integrity-check');"
```

---

## 3. Data Export & User Privacy Requests

### 3.1 Exporting User Data (JSON)
```bash
curl -X POST http://127.0.0.1:8000/api/memory/export \
  -H "Content-Type: application/json" \
  -H "X-Tenant-ID: default" \
  -d '{"format": "json"}' > export_memories.json
```

### 3.2 Hard Deletion with Cascade (Right to be Forgotten)
```bash
curl -X DELETE http://127.0.0.1:8000/api/memory/items/{memory_id} \
  -H "X-Tenant-ID: default"
```
This permanently deletes the record, cleans the FTS index, and invalidates all derived knowledge edges.

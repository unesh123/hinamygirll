# 38 — Disaster recovery and rollback

## Current status

- No staging/production deployment exists yet.
- Restore drill: **not executed**
- Rollback procedure: documented for future releases

## Intended procedure

1. Keep previous artifact (container image or release directory)  
2. On failed deploy: point reverse proxy/service unit back to previous artifact  
3. Database: forward-only migrations with documented downgrade notes; restore from encrypted backup if migration corrupts data  
4. Do not improvise destructive SQL  
5. Preserve audit tombstones during delete-all  

## Backup policy (target)

- Daily logical backup of PostgreSQL  
- Encrypted at rest  
- Retention aligned with privacy docs  
- One staging restore test before claiming backup readiness  

# 36 — UpCloud deployment runbook

## Preconditions

1. Owner sets UpCloud provisioning gates  
2. Inventory existing resources (avoid duplicates)  
3. Domain or temporary HTTPS strategy decided by owner  
4. Secrets injected via environment/secret store (never git)  
5. Working tree committed/tagged for reproducibility (owner action)

## Offline-safe steps completed

- Infra folder + Terraform example created
- Architecture/runbook/cost register/DR docs written

## Deploy sequence (when authorized)

1. Validate tests locally  
2. Build web + API artifacts  
3. Provision staging server/DB  
4. Configure reverse proxy + TLS  
5. Apply DB schema/migrations  
6. Smoke: health, mock text, WS mock, privacy auth  
7. Optional capped real-provider smoke  
8. Record resource IDs in cost register  

## Teardown

Require explicit confirmation; never auto-destroy. Export data before trial expiry.

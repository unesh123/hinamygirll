# 34 — Cost and capacity report

## Measured in this continuation

| Item | Measurement |
|---|---|
| Gemini calls | 0 |
| Azure Speech calls | 0 |
| UpCloud resources created | 0 |
| Mock offline eval cases | ≥10 corpus items |
| Playwright workers used for green run | 2 |

## Separated cost domains (planning)

1. UpCloud compute / DB / storage / egress  
2. Gemini tokens  
3. Azure Speech seconds  
4. Observability (if added)  

Promotional UpCloud credit **was not observed** in this session; do not assume balance or expiry.

## Capacity

- No mock load test numbers claimed beyond existing unit/e2e suites.
- Session memory remains bounded (in-process + optional durable DB).

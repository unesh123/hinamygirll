---
name: high-frequency-rss-ingestion-architect
description: High-frequency data ingestion feeding 3-Set RAG (Regulatory, Memory, Arbitrage), spatial complexity bounds, and local knowledge synchronization.
---

# High-Frequency RSS Ingestion Architect

## Core Components
- **Ingestion Pipeline**: Polling RSS/Atom feeds with deduplication and backoff.
- **3-Set RAG Matrix**:
  - Regulatory / Policy streams
  - Quasi-Crystalline Memory index
  - Real-time Arbitrage / Signal routing
- **Storage & Synchronization**: Local SQLite/Postgres vector persistence with automated markdown vault sync.

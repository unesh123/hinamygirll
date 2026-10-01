# Security Policy & Threat Model

## Mitigations (GHSA-w5fx-fh39-j5rw)
- Model-generated paths never establish security boundaries.
- Filesystem writes outside designated workspace roots are blocked.
- DNS, TCP, and network egress are governed by allowlists.
- Environment secrets are scrubbed before child process execution.

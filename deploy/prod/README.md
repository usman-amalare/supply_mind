# Production deployment

**Status: Proposed. Not implemented and not deployed.**

The master prompt describes one VPS, Docker Compose, Caddy for TLS, PostgreSQL 16 with a volume, and nightly `pg_dump` to S3-compatible storage. Those files and that host do not exist yet.

Do not invent backup credentials, DNS records, or a claim that a deploy succeeded. Add the production compose file in the deployment stage and record the result in `IMPLEMENTATION_PLAN.md`.

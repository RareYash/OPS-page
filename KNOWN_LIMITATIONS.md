# Known Limitations & Scaling Strategy — Newtonite Ops

> **Document Status:** Complete & Reviewed

This document details explicit technical boundaries, architectural trade-offs, and intentional non-goals accepted for Newtonite Ops v1.0, along with the operational roadmap to scale beyond current limits.

---

## 1. Current Boundaries & Accepted Trade-Offs

### A. Single-Region PostgreSQL Database
- **Limitation:** The system operates on a single primary PostgreSQL 16 database instance. All writes and reads pass through the primary node.
- **Why Accepted:** Adding multi-region replication or distributed transaction coordinators (e.g. CockroachDB, Spanner) introduces split-brain hazards, complex quorum configurations, and cross-region latency overhead that are unnecessary for an internal company tool serving hundreds to thousands of users.
- **Scale Plan:** Read-heavy load (search and list queries) can be offloaded to read replicas using PostgreSQL streaming replication, with writes directed strictly to the primary node.

### B. In-App Notifications Only
- **Limitation:** Notifications are generated, stored in the PostgreSQL `notifications` table, and retrieved via the in-app notification center. External email (SMTP/SES) and Slack webhook deliveries are not dispatched in v1.0.
- **Why Accepted:** The core objective of the async outbox worker was to demonstrate transaction safety, `SKIP LOCKED` batch consumption, exponential backoff, stuck job reclamation, and deduplication. External third-party messaging transports introduce external API rate limits and network flakiness unrelated to core concurrency mechanics.
- **Scale Plan:** Plug in external delivery adapters within `app/worker/outbox_worker.py` handlers (`send_smtp_email`, `send_slack_webhook`) with circuit-breaker protections.

### C. Keyset Pagination (No Arbitrary Page Jumping)
- **Limitation:** List views utilize keyset cursor pagination (`(updated_at, id)`). Users can navigate forward and "Load More", but cannot click to jump directly to arbitrary distant page numbers (e.g. "Jump to Page 84").
- **Why Accepted:** `OFFSET` pagination causes severe $O(N)$ query degradation on large tables (50,000+ items) and suffers from item shifting when rows are inserted or updated during pagination.
- **Scale Plan:** Keyset pagination is standard for modern feed architectures (GitHub, Slack, Twitter). Total item estimates are returned via estimated row counts when approximate totals are needed.

### D. Server-Side Session Storage in PostgreSQL
- **Limitation:** User sessions are stored in the `sessions` table in PostgreSQL. Every authenticated request verifies the session token hash in the database.
- **Why Accepted:** Server-side database sessions provide immediate revocation on logout or deactivation, with zero token replay vulnerability (unlike stateless JWTs which cannot be revoked without a blacklist). At our current operational scale, the index lookup on `sessions.token_hash` takes under 0.04 ms.
- **Scale Plan:** If API throughput exceeds 10,000 requests per second, session validation can be migrated to a Redis cluster or edge cache with pub/sub invalidation channels.

### E. User Management via Seed and Admin CLI (No Public Self-Signup)
- **Limitation:** There is no public user registration page. Users and memberships are provisioned via the seed script (`python -m app.seed`) or administrator tools.
- **Why Accepted:** Newtonite Ops is an internal enterprise operations tracking platform. In corporate enterprise systems, accounts are provisioned by IT administration, SCIM, or corporate single sign-on (SSO/SAML/OIDC).

---

## 2. Hardening & Scaling Roadmap (v2.0)

| Area | Current State (v1.0) | Target State (v2.0) |
|---|---|---|
| **Identity** | Argon2id + DB Sessions | OIDC / SAML 2.0 integration (Okta, Google Workspace) |
| **Real-Time** | 10s-30s Polling + Window Focus Refetch | Server-Sent Events (SSE) or WebSockets for live status badge updates |
| **Outbox Scaling** | Single Python worker threadpool | Partitioned outbox channels with multi-worker consumer groups |
| **Audit Log Archival** | PostgreSQL append-only partition | Cold storage archiving to S3 Parquet format after 365 days |
| **Read Scaling** | Connection pooling (30 connections) | Read replicas + PgBouncer transaction-mode pooler |

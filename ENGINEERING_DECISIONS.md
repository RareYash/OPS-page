# Architectural & Engineering Decisions — Newtonite Ops

This document outlines the core technical decisions made during the design and construction of Newtonite Ops, including alternatives considered, trade-offs accepted, and rationale.

---

## Decision 1: Synchronous SQLAlchemy 2.0 with Psycopg 3 vs. Async SQLAlchemy

### Context
FastAPI natively supports `async def` endpoints, and async SQLAlchemy is widely used for Python web microservices. We had to choose between synchronous transaction handling or asynchronous database sessions.

### Decision
We chose **Synchronous SQLAlchemy 2.0 with Psycopg 3** and threadpool connection pooling (`pool_size=20, max_overflow=10`).

### Trade-offs & Rationale
- **Clarity of Transaction Scopes:** Concurrency bugs, optimistic locking, and atomic row updates (`FOR UPDATE SKIP LOCKED`, conditional atomic `UPDATE ... RETURNING`) are much easier to reason about when transactions have strict, deterministic thread-bound lifetimes.
- **Rollback Guarantees:** Synchronous context managers guarantee a single commit on clean exit and automatic rollback on any uncaught exception without subtle task-cancellation race conditions.
- **Performance Reality:** For a company internal tool serving hundreds to thousands of users, a properly configured sync pool with connection pre-pinging easily handles hundreds of requests per second with <5ms latency. Async adds debugging complexity and event-loop blocking hazards without measurable throughput benefits on relational row-locking transactions.

---

## Decision 2: Transactional Outbox Pattern via PostgreSQL vs. Redis / Celery / Kafka

### Context
Mutations (work assignment, transitions, comments) trigger downstream asynchronous events such as notifications and audit dispatch. We evaluated Celery + Redis, Kafka, and a relational Transactional Outbox.

### Decision
We chose a **PostgreSQL Transactional Outbox** polled by a dedicated Python worker using `FOR UPDATE SKIP LOCKED`.

### Trade-offs & Rationale
- **Dual-Write Problem Elimination:** If an API saves an item to PostgreSQL and then attempts to push an event to Redis or Kafka, a network hiccup or crash leaves the database modified with lost events. By writing the event to the `outbox` table in the exact same database transaction, atomicity is guaranteed by PostgreSQL WAL.
- **Zero Additional Infrastructure:** Eliminating Redis/Celery removes two separate points of failure, authentication credentials, network topologies, and container orchestration overhead.
- **Concurrency Safety via Postgres:** PostgreSQL's `SKIP LOCKED` feature allows worker pools to process batches concurrently without locking each other or deadlocking.
- **Deduplication at the Target:** Downstream notification rows feature a unique `dedupe_key` constraint, delivering true at-least-once processing with exactly-once end results.

---

## Decision 3: Keyset (Cursor-Based) Pagination vs. OFFSET / LIMIT

### Context
Listing work items across teams needs to support tens of thousands of items smoothly under active mutations.

### Decision
We chose **Keyset Pagination on `(updated_at, id)`** encoded as an opaque URL-safe Base64 token.

### Trade-offs & Rationale
- **Consistent $O(1)$ Performance:** `OFFSET 10000` forces the database engine to scan and discard 10,000 index tuples on every request. Keyset pagination performs an index seek directly to `(updated_at, id) < (cursor_time, cursor_id)` and reads only the requested limit (e.g., 20 rows) in under 0.1 ms regardless of page depth.
- **Stability Under High Concurrency:** When multiple operators add or modify items continuously, `OFFSET` causes items to shift positions, causing users to see duplicate items or miss items when paginating. Keyset pagination anchors to record timestamps and primary keys, maintaining deterministic pages.
- **Accepted Trade-off:** Users cannot jump arbitrarily to "page 47". For operational tracking, linear continuous scroll or "Load More" meets all requirements.

---

## Decision 4: Cross-Team Resource Lookups Return 404 Not Found vs. 403 Forbidden

### Context
When a user attempts to access an item that belongs to another team of which they are not a member, the API could return either `403 Forbidden` or `404 Not Found`.

### Decision
All item lookups outside the user's active team memberships return **`404 Not Found`** via `get_item_for_user()`.

### Trade-offs & Rationale
- **Information Disclosure / BOLA Prevention:** Returning `403 Forbidden` informs an attacker that a resource with that UUID exists, leaking organizational metadata, project sizes, and UUID validity. Returning `404 Not Found` makes unauthorized cross-team items completely invisible and indistinguishable from non-existent IDs.
- **Strict Role Boundaries:** `403 Forbidden` is reserved exclusively for authenticated members of the item's team who lack sufficient role privileges to perform a specific mutation (e.g. a `viewer` attempting to create an item, or a `member` attempting to assign another user).

---

## Decision 5: Argon2id Password Hashing vs. Bcrypt

### Context
User authentication credentials must be hashed securely against brute-force and GPU/ASIC acceleration attacks.

### Decision
We chose **Argon2id** (`argon2-cffi`), the winner of the Password Hashing Competition (PHC).

### Trade-offs & Rationale
- **GPU & ASIC Resistance:** Bcrypt is memory-hard only to a very low degree (4 KB), making it susceptible to modern GPU-based cracking clusters. Argon2id incorporates both time and memory hardness (configured to 64 MB of RAM and multiple iterations), rendering parallel hardware attacks economically impractical.
- **Side-Channel Defense:** Argon2id combines Argon2d (data-dependent memory access for maximum GPU resistance) and Argon2i (data-independent access to thwart side-channel timing attacks), providing defense against modern cryptographic exploits.

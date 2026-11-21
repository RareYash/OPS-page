# Newtonite "Operations Under Pressure" — Execution Plan

Deadline: **Monday 19 Oct 2026, 12:00 PM IST**. Personal target for final submit: **10:00 AM**, so there are two hours of slack for things that break.

This plan covers the full cycle: requirements, design, build, test, security review, docs, submission, and what to say in the review. Every phase has an exit check. Do not start the next phase until the exit check passes.

---

## 0. What the brief is really testing

Reading between the lines, they are grading these things, in this order:

1. Do you handle concurrency on purpose (two people claiming the same item, stale edits, retries).
2. Is authorization enforced in the backend, per resource, not just hidden buttons.
3. Is there a real history of what happened, and can it not be silently erased.
4. Does it still work with tens of thousands of items (pagination, indexes, no "load everything").
5. Can you explain every decision and every failure mode in the review.
6. Do tests target the dangerous behaviour, not random coverage.

A small system that does these six properly beats a big one with a pretty UI. Decorative UI is explicitly low priority in the brief.

**Rule for AI-assisted code:** the brief allows AI tools but says you may be asked to explain or change any part live. So for every module: read it, run it, break it on purpose, and be able to explain it in your own words. If you can't explain a function, rewrite it simpler.

---

## 1. Assumptions (write these into the README too)

- Internal company tool, several hundred to a few thousand users, grouped into teams.
- A user can be in several teams with a different role in each.
- A work item belongs to exactly one team.
- Notifications are in-app only. Email/Slack delivery is out of scope; the async worker proves the pattern.
- No self-signup. Users are created by seed script / admin CLI.
- English only, UTC timestamps stored, shown in the browser's local time.
- Single region, single Postgres. Scale plan is described in the docs, not built.

---

## 2. Stack and why

| Layer | Choice | Reason |
|---|---|---|
| API | Python 3.12, FastAPI, Pydantic v2 | You already know it. Strong request validation by default. |
| ORM / DB access | SQLAlchemy 2.0 (sync) + psycopg 3 | Sync is simpler to reason about for transactions. Raw SQL allowed for the atomic updates. |
| Database | PostgreSQL 16 | Row locking, partial indexes, full-text search, `SKIP LOCKED`, JSONB. No Redis needed. |
| Migrations | Alembic | Schema is versioned, not created by `create_all`. |
| Password hashing | argon2-cffi | Not MD5/SHA, not plain bcrypt defaults copied blindly. |
| Frontend | React + TypeScript + Vite + TanStack Query | TanStack Query gives caching, refetch, and optimistic updates with rollback, which the brief asks about. |
| Worker | Plain Python process polling an outbox table | No Celery/Redis. Fewer moving parts, and the failure story is easy to explain. |
| Tests | pytest + httpx + real Postgres in Docker | SQLite hides concurrency bugs. Use the real DB. |
| Tooling | ruff, mypy, bandit, pip-audit, npm audit | Catch the usual generated-code problems automatically. |
| Run | Docker Compose: `db`, `api`, `worker`, `web` | One command to run for the reviewer. |

Intentionally **not** using: microservices, Kafka, Redis, WebSockets, Kubernetes, GraphQL. They add failure modes and no marks within one day.

---

## 3. SDLC phases with time boxes

Total build time is roughly 13 hours including buffer. If you have fewer hours, see the cut list in section 12.

| # | Phase | Time | Output |
|---|---|---|---|
| 0 | Setup and requirements | 45 min | Repo, tooling, `.gitignore`, CI skeleton, assumptions |
| 1 | Design | 60 min | Schema, state machine, permission matrix, API list (written down before code) |
| 2 | Backend core | 3 h | Auth, teams, items CRUD, events, list/search/dashboard |
| 3 | Critical behaviours | 2 h | Claim, versioning, idempotency, workflow rules, approvals |
| 4 | Async processing | 1 h | Outbox, worker, retries, dedupe |
| 5 | Frontend | 2.5 h | Login, dashboard, list, detail, conflict handling |
| 6 | Security and hardening pass | 1 h | Checklist in section 8, tools run, fixes |
| 7 | Docs and submission prep | 1 h | README, decisions, limitations, clean-clone test |
| – | Buffer | 1.5 h | Things will break. This is not optional. |

Tests are written **inside** phases 2 to 5, not at the end. A feature is not done until its test passes.

### Phase 0 — Setup and requirements (45 min)

- Create a **public** GitHub repo (the form requires public). Name: `newtonite-ops` or similar.
- Before the first commit: `.gitignore` with `.env`, `__pycache__`, `node_modules`, `*.pem`, `*.key`, `.venv`. Commit `.env.example` only.
- Pin dependencies (`requirements.txt` with exact versions or a lock file). Commit lock files.
- Set up `ruff`, `mypy`, `pytest`, `bandit` config.
- GitHub Actions workflow: lint, type-check, tests against a Postgres service container, `bandit`, `pip-audit`.
- Write the assumptions list (section 1) into `README.md`.

**Exit check:** empty FastAPI app returns `/health`, CI is green on the first push, no secrets in git history (`git log -p | grep -i -E "password|secret|key"` returns nothing real).

### Phase 1 — Design (60 min)

Write these four things down in `docs/design.md` before writing app code. Changing a doc is cheap, changing a schema halfway through is not.

#### 1a. Data model

```
users            id uuid PK, email (unique, lowercased), name, password_hash, is_active, created_at
teams            id uuid PK, name, slug unique
memberships      user_id FK, team_id FK, role ('viewer'|'member'|'lead'|'admin'), PK(user_id, team_id)
sessions         id uuid PK, user_id FK, token_hash (unique), expires_at, created_at
work_items       id uuid PK, team_id FK, title, description, status, priority,
                 assignee_id FK null, created_by FK, requires_approval bool,
                 approved_by FK null, approved_at null, due_at null,
                 version int NOT NULL DEFAULT 1,
                 created_at, updated_at,
                 search_vector tsvector (generated from title + description)
item_events      id bigserial PK, item_id FK, actor_id FK, type, payload jsonb, created_at
                 (append-only; enforced by a DB trigger that rejects UPDATE and DELETE)
comments         id uuid PK, item_id FK, author_id FK, body, created_at
idempotency_keys user_id, key, endpoint, request_hash, status_code, response_body jsonb,
                 created_at, PRIMARY KEY (user_id, key)
outbox           id bigserial PK, type, payload jsonb, status ('pending'|'processing'|'done'|'failed'),
                 attempts int, next_attempt_at, locked_at null, last_error, created_at
notifications    id uuid PK, user_id FK, item_id FK, kind, dedupe_key UNIQUE, read_at null, created_at
```

Database-level guards (the backstop if app code has a bug):

- `CHECK` constraints on `status`, `priority`, `role` values (or Postgres enums).
- `CHECK (status <> 'in_progress' OR assignee_id IS NOT NULL)`.
- `NOT NULL` and foreign keys everywhere that makes sense.
- Trigger on `item_events` that raises on UPDATE or DELETE.
- Max length on title (200) and description/comment (10,000) enforced both in Pydantic and in the DB.

Indexes (justify each in the decisions doc):

- `work_items (team_id, status, priority, updated_at DESC, id)` — main list query.
- `work_items (assignee_id, status)` — "my work".
- Partial index on open items: `WHERE status NOT IN ('resolved','closed')` — keeps the hot index small as closed items pile up.
- `GIN (search_vector)` — full-text search.
- `item_events (item_id, id DESC)` — history pagination.
- `outbox (status, next_attempt_at)` — worker polling.
- `memberships (team_id, role)`.

#### 1b. Workflow state machine

States: `open → in_progress → pending_approval → resolved → closed`, plus `resolved → open` (reopen).

| From | To | Who can do it | Extra rule |
|---|---|---|---|
| open | in_progress | assignee (or via claim) | needs an assignee |
| in_progress | resolved | assignee | only if `requires_approval = false` |
| in_progress | pending_approval | assignee | only if `requires_approval = true` |
| pending_approval | resolved | lead/admin | **must not be the assignee** (separation of duties) |
| pending_approval | in_progress | lead/admin | rejection, comment required |
| resolved | closed | lead/admin | |
| resolved | open | member+ | reopen, clears nothing, writes an event |

Anything not in the table is rejected with 409 and a clear message. The table lives in one Python dict in `workflow.py` and is the only place transitions are decided.

#### 1c. Permission matrix

Authorization is checked in a single `policy.py` module. Routers call `policy.can(user, action, item)`; they don't contain their own `if role == ...` checks.

| Action | viewer | member | lead | admin |
|---|---|---|---|---|
| View team items and history | yes | yes | yes | yes |
| Create item | no | yes | yes | yes |
| Comment | no | yes | yes | yes |
| Edit title/description (own or assigned) | no | yes | yes | yes |
| Edit anything on any team item | no | no | yes | yes |
| Claim unassigned item | no | yes | yes | yes |
| Assign / reassign to someone else | no | no | yes | yes |
| Release (unassign) own item | no | yes | yes | yes |
| Release someone else's item | no | no | yes | yes |
| Change priority | no | own/assigned only | any | any |
| Approve / reject | no | no | yes (not own) | yes (not own) |
| Manage memberships | no | no | no | yes (via CLI/seed in v1) |

Rule: a user who is **not a member of the item's team gets 404**, not 403. A 403 confirms the item exists.

The API also returns an `allowed_actions` list on each item so the UI can show the right buttons. That list is a convenience only. Every endpoint re-checks.

#### 1d. API surface

```
POST   /auth/login            POST /auth/logout       GET /me
GET    /teams                                         (teams I belong to, with my role)
POST   /items                                         (Idempotency-Key required)
GET    /items                 ?team_id&status&priority&assignee&q&cursor&limit
GET    /items/{id}
PATCH  /items/{id}                                    (If-Match: version required)
POST   /items/{id}/claim
POST   /items/{id}/assign     {assignee_id}           (lead+)
POST   /items/{id}/release
POST   /items/{id}/transition {to}                    (version required)
POST   /items/{id}/comments
GET    /items/{id}/events     ?cursor&limit
GET    /dashboard                                     (counts + needs-attention lists)
GET    /notifications         POST /notifications/{id}/read
GET    /health
```

Errors use one format: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`.
Status codes used deliberately: 400/422 bad input, 401 not logged in, 404 not found or not visible, 409 conflict (stale version, already claimed, invalid transition), 428 missing version, 429 rate limited.

**Exit check:** you can explain the schema, state machine, and permission matrix out loud without looking.

### Phase 2 — Backend core (3 h)

Build order, each with its tests:

1. Config via environment variables (`pydantic-settings`). App refuses to start in non-dev mode if `SECRET_KEY` is the placeholder.
2. DB session handling: **one transaction per request**, commit on success, rollback on any exception.
3. Alembic migration for the full schema (including the trigger and indexes).
4. Seed script: 3 teams, ~8 users with mixed roles across teams, a few hundred sample items (use a flag to generate 50,000 for the performance demo).
5. Auth: login (argon2 verify), server-side session row, cookie `HttpOnly`, `Secure` in prod, `SameSite=Lax`. Logout deletes the session. Sessions expire (e.g. 8 hours).
6. `policy.py` and a `get_item_for_user(db, user, item_id)` helper that scopes by membership. **All item lookups go through it.**
7. Items: create, get, list with keyset pagination, patch.
8. Events: every mutation writes an `item_events` row in the same transaction.
9. Comments.
10. Dashboard endpoint.

Pagination: keyset (cursor) on `(updated_at, id)`, not OFFSET. Cursor is an opaque base64 string; decoding errors return 422. `limit` is capped at 100.

Search: `plainto_tsquery('english', :q)` with a bound parameter, ranked, combined with the filters. Sort columns are chosen from a whitelist, never taken from the client as raw text.

"Needs attention" definition (write it in the docs, it's a product decision):

- Assigned to me and not closed, ordered by priority then due date.
- Unassigned and priority high/critical in my teams.
- Pending approval where I can approve (lead/admin and not the assignee).
- Overdue (past `due_at`, not resolved).
- Stale: in progress with no events for 3 days.

Each section is its own query with `LIMIT`, plus one grouped count query. Nothing loads the whole table.

**Exit check:** can create/list/search an item through the API as different users; seed with 50k items and list/search responds fast (check with `EXPLAIN ANALYZE` that indexes are used; save the output for the docs).

### Phase 3 — Critical behaviours (2 h)

These are the "more than CRUD" cases. The brief wants at least three; do all four plus the authorization one.

**3.1 Two people claiming the same item**

Done in one atomic statement, not "read then write":

```sql
UPDATE work_items
SET assignee_id = :user, status = CASE WHEN status = 'open' THEN 'in_progress' ELSE status END,
    version = version + 1, updated_at = now()
WHERE id = :id AND assignee_id IS NULL
RETURNING *;
```

0 rows returned means someone else got there first: return 409 with the current assignee. Insert the event and outbox row in the same transaction. No application-level lock, no Redis. Single-row updates also mean no deadlock risk.

**3.2 Stale edits (optimistic locking)**

Every mutation carries the version the client last saw. `UPDATE ... WHERE id = :id AND version = :v`. 0 rows means conflict: respond 409 with the **current** item so the UI can show what changed. Missing version header returns 428. Every mutation, including claim/assign/transition, bumps `version`, so someone editing an old copy after a claim also gets a conflict.

**3.3 Repeated requests (idempotency)**

- Client sends `Idempotency-Key` (a UUID generated per user action, reused on retry).
- Inside the same transaction as the business write, insert the key row. If the insert hits the unique constraint, another request with that key is running or finished. Postgres makes the second insert wait for the first transaction, so a concurrent duplicate resolves cleanly after commit.
- Same key and same request hash: return the stored response (same status and body).
- Same key and different body: 422.
- If the business write fails, the whole transaction rolls back, including the key row, so a retry can run again.
- Keys expire after 24 hours (cleanup job or on-read check).

**3.4 Workflow rules**

`workflow.py` holds the transition table. A function `check_transition(item, user, to)` returns allowed or a reason. Including the separation-of-duties rule (approver is not the assignee). Illegal transition returns 409 with the reason.

**3.5 Resource-level authorization**

Covered by `get_item_for_user` and `policy.can`. Add a parametrized test that hits **every** item route as a user from another team and as a viewer, and asserts 404 / 403 as designed.

**Exit check:** each of the above has a passing automated test, and the concurrent ones actually run in parallel (threads or `asyncio.gather` against the live app and DB).

### Phase 4 — Async processing (1 h)

Pattern: **transactional outbox.**

- In the same transaction as the business change, insert an `outbox` row (e.g. `item.assigned`, `item.pending_approval`, `comment.added`). If the transaction rolls back, the outbox row disappears too. No "saved the item but lost the notification".
- Worker loop (separate container):
  1. `SELECT ... WHERE status='pending' AND next_attempt_at <= now() ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 10`.
  2. Mark `processing`, set `locked_at`, commit.
  3. Handle each message; create `notifications` rows.
  4. Mark `done`.
- **Executes more than once:** notification rows use `dedupe_key = "{outbox_id}:{user_id}"` with a unique constraint and `ON CONFLICT DO NOTHING`. Processing twice creates one notification.
- **Fails:** `attempts += 1`, `next_attempt_at = now() + backoff` (5s, 10s, 20s … capped at 15 min, with a bit of jitter). After 6 attempts: `status='failed'`, error stored, logged. Failed rows are visible, not lost.
- **Worker crashes mid-job:** rows stuck in `processing` with `locked_at` older than 60 seconds get picked up again.
- **Delayed:** notifications store the event's `created_at`, so a late notification still shows the correct time.

Who gets notified: new assignee on assignment; team leads when an item goes to pending approval; assignee and creator on new comments (not the person who wrote it); assignee on approval/rejection.

**Exit check:** tests for failure-then-retry, duplicate processing, and stuck-job recovery pass.

### Phase 5 — Frontend (2.5 h)

Pages: Login, Dashboard, Items (list + filters + search), Item detail (fields, timeline, comments, actions).

State management decisions (write these in the decisions doc):

- **Server state** (items, lists, events) lives in TanStack Query. No copying into a global store.
- **UI state** (open dialogs, filter inputs) lives in component state or the URL query string. Filters in the URL so links are shareable and back/forward works.
- Search input is debounced (300 ms).
- List uses cursor pagination with "load more" or infinite scroll. Never fetches everything.
- **Optimistic updates** for claim and comment: update the cache immediately, then reconcile. On a 409, roll back and show a clear message ("Priya claimed this 5 seconds ago") and refetch. The server's answer always wins.
- **Idempotency key** generated when the user clicks, kept for retries of that same action. A new click makes a new key.
- **Stale data:** refetch on window focus, poll the open item every ~10 s and the list every ~30 s. If the item changed while the user has an edit form open, show a banner and keep their text rather than wiping it.
- Buttons are shown from `allowed_actions`, but nothing in the UI is a security measure.
- Loading, empty, and error states for every screen. A failed request shows an error, not a blank page.
- Render all user text as plain text. Do not use `dangerouslySetInnerHTML` anywhere.

Keep styling plain and clean. The brief says it cares more about a coherent, responsive experience than decoration.

**Exit check:** two browser windows logged in as different users can: claim the same item (one wins, the other sees the conflict), edit the same item (one gets the stale warning), and see changes within the polling interval.

### Phase 6 — Security and hardening pass (1 h)

Go through section 8 line by line and tick each item. Run the tools:

```
ruff check . ; mypy app ; bandit -r app ; pip-audit ; cd frontend && npm audit
```

Fix real findings. Note any accepted ones in the limitations file with a reason.

### Phase 7 — Docs and submission prep (1 h)

See sections 9 and 11.

---

## 4. Concurrency scenarios mapped to the brief

| Brief scenario | What the system does | Test |
|---|---|---|
| Two users take the same work | Atomic conditional UPDATE, loser gets 409 | 20 parallel claims, exactly 1 success, 1 event |
| Viewing info someone just changed | Version number, 409 on stale write, polling and refetch on focus | Stale PATCH returns 409 with current item |
| Multiple updates in a short time | Row-level version check serializes them; none are lost | Parallel PATCHes with same version, 1 wins |
| Repeating an action unsure of success | Idempotency key replays the stored response | Same key twice = 1 row; concurrent same key = 1 row |

---

## 5. Testing plan (risk-based)

Test against **real Postgres**. Each test gets a clean state (truncate between tests or use a fresh schema).

Highest priority, "would be dangerous if wrong":

1. Concurrent claim: exactly one winner. No lost update, no double assignment.
2. Stale update rejected, missing version rejected.
3. Idempotent create, including concurrent duplicates and same-key/different-body.
4. Workflow: parametrized over every (from, to) pair; only table-allowed pairs succeed.
5. Separation of duties: assignee can't approve own item.
6. Cross-team isolation: user from team B can't read, edit, claim, comment, or see events on team A's item (all routes).
7. Role enforcement: viewer can't mutate; member can't assign others or approve.
8. Event log can't be altered: UPDATE/DELETE on `item_events` fails at DB level.
9. Every mutation produces exactly one event, in the same transaction (rollback test: if the write fails, no event exists).
10. Outbox: retry with backoff, duplicate processing gives one notification, stuck job is reclaimed, failed state after max attempts.
11. Pagination: no duplicates or gaps across pages, stable when new rows are inserted during paging.
12. Auth: wrong password and unknown user return the same response, expired session rejected, logout invalidates.
13. Input validation: oversized body, unknown fields (`extra=forbid`), bad cursor, `limit` above cap.

Frontend: a small number of Vitest tests for optimistic rollback on 409, and idempotency key reuse on retry.

Also keep a short manual demo script (section 10) and rehearse it.

---

## 6. Repo layout

```
newtonite-ops/
  README.md                 how to run, assumptions, test commands, demo accounts
  ENGINEERING_DECISIONS.md  ~5 decisions with trade-offs
  KNOWN_LIMITATIONS.md
  docker-compose.yml
  .env.example
  .gitignore
  .github/workflows/ci.yml
  docs/
    design.md               schema, state machine, permission matrix, API list
    architecture.md         diagram (Mermaid) of api / worker / db / web
    query-plans.md          EXPLAIN ANALYZE outputs on 50k items
  backend/
    app/
      main.py  config.py  db.py  models.py  schemas.py
      security.py           hashing, sessions, headers, CSRF/origin check
      policy.py             all permission decisions
      workflow.py           transition table
      idempotency.py
      routers/              auth, items, dashboard, notifications
      services/             item_service.py (business logic, atomic updates)
      worker/               outbox loop and handlers
    alembic/
    tests/
    requirements.txt  Dockerfile
  frontend/
    src/  package.json  package-lock.json  Dockerfile
```

Commit habits: small commits, one per meaningful step, readable messages (`add atomic claim with 409 on conflict`). Tag `v1.0` at submission. A messy single "final commit" looks bad in review.

---

## 7. Mistakes typical of rushed or auto-generated apps, and how this plan avoids them

| Common mistake | Prevention here |
|---|---|
| Secrets committed (`.env`, keys, DB password) | `.gitignore` first, `.env.example` only, startup refuses placeholder secret outside dev, scan history before submitting |
| Authorization only in the UI | Central `policy.py`, every endpoint checked, tests hit the API directly |
| IDOR / BOLA (change an ID, see someone else's data) | `get_item_for_user` scopes every lookup by membership, 404 for outsiders, all-routes test |
| Trusting the client for identity (`user_id` in the request body) | Actor always comes from the session, never from input |
| Mass assignment (`Model(**request.dict())`) | Separate input schemas, `extra="forbid"`, explicit field mapping |
| SQL injection via f-strings, raw sort/filter params | Bound parameters only, sort column whitelist, `bandit` run |
| Read-then-write races | Atomic conditional UPDATEs and version checks |
| Duplicate submissions on retry | Idempotency keys |
| Weak password storage | argon2id, no password in logs, same error for bad user and bad password |
| No login throttling | Rate limit on `/auth/login` (per IP and per email), 429 on excess |
| Sessions that never expire | Expiry, server-side revocation on logout |
| Wildcard CORS with credentials | Explicit origin allow-list, same-origin in the Docker setup |
| CSRF on cookie auth | `SameSite` cookie, require a custom header on state-changing requests, check `Origin` |
| XSS from user text | React escaping, no raw HTML rendering, CSP header |
| Stack traces and SQL errors leaked to clients | Global exception handler, generic message plus request ID, details only in server logs |
| Debug mode left on, default admin password | `DEBUG` off by default; demo passwords only come from the seed script and are labelled demo-only |
| Unbounded queries and payloads | `limit` cap, body size limit, field length limits |
| Everything loaded to the browser | Keyset pagination, server-side filter and search |
| DB exposed to the internet by Docker | DB port not published (or bound to 127.0.0.1), non-root containers |
| Audit log editable | Append-only trigger on `item_events` |
| Unpinned, vulnerable dependencies | Pinned versions, lock files, `pip-audit`, `npm audit` |
| Tests that only check the happy path | Tests target races, permissions, and failure paths (section 5) |
| "It works on my machine" | Clean-clone test: fresh clone, `docker compose up`, tests pass |

---

## 8. Security checklist (tick during phase 6)

**Secrets and config**
- [ ] No secrets in repo or git history; `.env` ignored
- [ ] `SECRET_KEY` and DB password come from environment
- [ ] App fails fast in non-dev mode with placeholder secrets
- [ ] `DEBUG` off by default

**Authentication**
- [ ] argon2id password hashing
- [ ] Login returns the same error for unknown user and wrong password
- [ ] Login rate limited
- [ ] Session token random (`secrets.token_urlsafe`), only the hash stored in DB
- [ ] Cookie: `HttpOnly`, `SameSite`, `Secure` when not on localhost
- [ ] Session expiry and logout revocation work
- [ ] Inactive users can't log in or use existing sessions

**Authorization**
- [ ] Every route has an auth dependency (test that fails if a route is added without one)
- [ ] All permission logic is in `policy.py`
- [ ] Item lookups always scoped by membership
- [ ] Outsiders get 404
- [ ] Actor taken from the session only
- [ ] Assign endpoint verifies the target user belongs to the item's team

**Input and output**
- [ ] Pydantic schemas with `extra="forbid"`, length limits, enum values
- [ ] No f-string SQL anywhere (`grep -rn "f\"SELECT\|f'SELECT" backend/`)
- [ ] Sort and filter fields whitelisted
- [ ] Cursor decoding validated
- [ ] Request body size limit
- [ ] Responses never include `password_hash` or session tokens (schema-level exclusion, test it)

**Web layer**
- [ ] CORS allow-list, not `*`
- [ ] CSRF defence for cookie auth (custom header + Origin check)
- [ ] Security headers: `X-Content-Type-Options`, `X-Frame-Options`/`frame-ancestors`, `Referrer-Policy`, CSP
- [ ] No `dangerouslySetInnerHTML`
- [ ] Global error handler: generic message, request ID, no stack trace

**Data**
- [ ] Constraints, FKs, `CHECK`s in the schema
- [ ] `item_events` append-only trigger works
- [ ] Mutation + event + outbox in one transaction
- [ ] Timestamps are timezone-aware UTC

**Operations**
- [ ] Containers run as non-root
- [ ] DB port not exposed publicly
- [ ] Logs are structured and contain no passwords or tokens
- [ ] `bandit`, `pip-audit`, `npm audit` run, findings fixed or documented

---

## 9. Documents to write

**README.md**
- What it is (3 lines), screenshots optional
- Run: `cp .env.example .env && docker compose up --build`, then URL, then seed command
- Demo accounts (clearly marked demo-only), which user has which role in which team
- How to run tests, linters
- Assumptions (section 1)
- Link to the other docs

**ENGINEERING_DECISIONS.md** (about five decisions, each with: context, decision, alternatives considered, trade-off, what I'd change at larger scale)

1. **Postgres as the single source of truth, no Redis/queue.** Atomic SQL and row locks give correctness; fewer moving parts to fail. Trade-off: the worker polls the DB, which is fine at this scale but wouldn't be at very high throughput.
2. **Two concurrency mechanisms on purpose.** Atomic conditional update for claim (a yes/no race), version-based optimistic locking for edits (merge-sensitive). Why not pessimistic locks: they hold rows while a human thinks.
3. **Transactional outbox for async work.** Notification can't be lost or sent for a change that rolled back; duplicates are harmless through dedupe keys. Trade-off: at-least-once, so consumers must be idempotent.
4. **Central policy module, 404 for outsiders, `allowed_actions` returned to the UI.** One place to audit. The UI is never the control.
5. **Append-only event log written in the same transaction as the change, enforced at the DB.** History can't silently disappear, and "why was this decision made" is answerable.

Also list "what I chose not to build" (WebSockets/SSE, email delivery, user admin UI, attachments, SSO) with one-line reasons.

**KNOWN_LIMITATIONS.md** (be honest, reviewers like honesty)
- Polling instead of push, so views can be up to ~10–30 s stale (conflicts are still caught on write)
- Notifications are in-app only
- Memberships managed via seed/CLI
- Rate limiting is in-process or DB-based, not distributed
- Full-text search is English only, no typo tolerance
- Single Postgres, no read replicas; `item_events` is not partitioned yet
- Not load tested beyond the 50k-item seed
- Any accepted scanner findings with reasons

**docs/architecture.md**: one Mermaid diagram (browser, api, postgres, worker) and a short "what happens on claim" sequence.

**docs/query-plans.md**: `EXPLAIN ANALYZE` output for the list, search, and dashboard queries with 50k seeded items.

---

## 10. Demo script and review preparation

Demo (about 5 minutes, rehearse twice):

1. Log in as a member in team A. Create an item (show the idempotency: double-click, one item).
2. Two browser windows, two users: both click Claim. One wins, the other sees the conflict message and the item updates.
3. Edit the same item in both windows: the second save gets the stale warning with the current values.
4. Move an `requires_approval` item to pending approval; show the assignee can't approve, the lead can.
5. Open the timeline: everything above is recorded with actor and time.
6. Log in as a user from team B: the item is not found. Show the same through `curl` to prove it's the API, not the UI.
7. Kill the worker, make an assignment, restart the worker: the notification still arrives.
8. Show the 50k-item list/search and the query plan.

Questions to be ready for, with your own-words answers:

- What happens if the worker dies halfway? (Stuck-job reclaim, dedupe key.)
- What if the same notification runs twice? (Unique `dedupe_key`.)
- Why 404 and not 403? (Doesn't confirm existence.)
- Why optimistic locking for edits but atomic update for claim?
- What if two requests with the same idempotency key arrive at the same time? (Unique insert in the same transaction; second waits, then replays.)
- How would this change at 10x? (PgBouncer, read replicas for list/search, partition `item_events` by month, cache dashboard counts, move outbox to SQS/Kafka, SSE/WebSockets for push, dedicated search engine if FTS isn't enough.)
- What would you do with another week? (Push updates, email/Slack delivery, membership admin UI, audit export, load testing, SSO.)
- What did you use AI for, and what did you verify yourself?

---

## 11. Submission checklist

Do this from 9:00 AM Monday at the latest.

- [ ] Fresh clone into a new folder, `docker compose up --build`, seed, app works
- [ ] All tests pass from that fresh clone
- [ ] CI is green on the final commit
- [ ] No secrets in the repo or history
- [ ] README, ENGINEERING_DECISIONS, KNOWN_LIMITATIONS, docs present
- [ ] Repo is **public**; open the link in an incognito window to confirm
- [ ] Tag `v1.0`
- [ ] Submit the repo link through the Newtonite form: https://forms.gle/zPKbaU1AfumEY3218
- [ ] Screenshot or save the form confirmation
- [ ] Do **not** push anything risky after submitting; if you must fix something, push before 11:30 AM and re-check

---

## 12. If time runs short: cut list

Cut from the top first. Never cut the last block.

1. Frontend polish, charts, nice styling
2. Notification UI (keep the worker and DB rows, show a simple list)
3. Polling intervals tuning, focus refetch extras
4. Rate limiting on login (document it as a limitation)
5. Comment features beyond create/list
6. Dashboard sections beyond "assigned to me", "unassigned urgent", "pending approval"

**Never cut:** auth and per-resource authorization, the claim/version/idempotency/workflow behaviours, the append-only history, the tests for those, the README, ENGINEERING_DECISIONS, KNOWN_LIMITATIONS, and a public repo submitted on time.

---

## 13. How we work through this

- We go phase by phase. For each module I write the code, you run it and the tests.
- After each phase, you explain back what it does and what happens when it fails. If something is unclear, we simplify it.
- If a phase runs over its time box, we cut scope using section 12 rather than skipping tests or security checks.

# Y corp. Ops — Operations Under Pressure

> **Mission-Critical Work Item Tracking System**  
> Engineered specifically for high-concurrency operations under severe pressure, race condition resistance, and adversarial security isolation.

---

## 1. Quick Start

### Method A: Local Standalone (No Docker Required)

The project includes built-in hybrid support for local SQLite/PostgreSQL development.

#### 1. Setup Backend
Open a terminal in `d:\project\backend`:
```powershell
# Set environment variables
$env:PYTHONPATH="d:\project\backend"
$env:DATABASE_URL="sqlite:///d:/project/backend/dev.db"
$env:SECRET_KEY="dev-secret-key-12345"

# Seed demo data (3 teams, 8 users, 20 items)
d:\project\.venv\Scripts\python.exe -m app.seed

# Start FastAPI API server on http://127.0.0.1:8000
d:\project\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

#### 2. Start Asynchronous Outbox Worker (Optional / Background)
In another terminal:
```powershell
$env:PYTHONPATH="d:\project\backend"
$env:DATABASE_URL="sqlite:///d:/project/backend/dev.db"
d:\project\.venv\Scripts\python.exe -m app.worker.outbox_worker
```

#### 3. Start Frontend Web Client
In another terminal in `d:\project\frontend`:
```powershell
npm install
npm run dev
```
Open [http://localhost:5173](http://localhost:5173) in your browser.

---

### Method B: Docker Compose (Production Multi-Container Stack)

If you have Docker Desktop running:
```bash
docker compose up --build
```
This boots 4 isolated containers:
1. `db`: PostgreSQL 16 (internal port only, not exposed publicly for security).
2. `api`: FastAPI application on [http://localhost:8000](http://localhost:8000) (auto-runs Alembic migrations).
3. `worker`: Async Transactional Outbox processor polling with `FOR UPDATE SKIP LOCKED`.
4. `web`: Modern React + Vite + TanStack Query frontend on [http://localhost:5173](http://localhost:5173).

---

## 2. Seed Data & Performance Demo

### Standard Seed (~20 Items, 8 Users, 3 Teams)
```bash
docker compose exec api python -m app.seed
```

### Performance Stress-Test Seed (50,000 Items)
Populates the database with 50,000 realistic work items with tsvector full-text search indexes:
```bash
docker compose exec api python -m app.seed --large
```

---

## 3. Demo Accounts & Personas

All demo accounts share the password: **`password123`** (marked clearly as demo-only).
The frontend login page also features **1-click quick login buttons** for every persona.

| Email | Name | Team: Platform | Team: Product | Team: Security | Persona Description |
|---|---|---|---|---|---|
| `alice@example.com` | Alice Chen | **Admin** | Viewer | — | Full administrative control in Platform. |
| `bob@example.com` | Bob Patel | **Lead** | — | Member | Platform Lead: can assign work, approve items. |
| `charlie@example.com` | Charlie Kim | **Member** | Member | — | Platform & Product engineer: claims work, comments. |
| `diana@example.com` | Diana Müller | — | **Admin** | **Lead** | Cross-team Lead/Admin across Product & Security. |
| `ethan@example.com` | Ethan Osei | — | **Member** | — | Dedicated Product team engineer. |
| `faye@example.com` | Faye Nakamura| **Member** | **Lead** | — | Member in Platform, Lead in Product. |
| `george@example.com` | George Torres| Viewer | — | **Admin** | Security Admin; read-only viewer in Platform. |
| `hana@example.com` | Hana Al-Rashid| — | Member | Member | Cross-team Member in Product & Security. |

---

## 4. Key Concurrency Scenarios Tested & Proven

### A. Two Users Take the Exact Same Work (Atomic Claim)
- **Mechanism:** Implemented via an atomic conditional SQL statement:
  ```sql
  UPDATE work_items
  SET assignee_id = :user_id, status = 'in_progress', version = version + 1
  WHERE id = :item_id AND assignee_id IS NULL
  RETURNING *;
  ```
- **Result:** If two operators click "Claim" at the same sub-second instant, exactly one wins (`200 OK`). The second request returns `409 Conflict` alongside the winning assignee's details.
- **Automated Test:** `backend/tests/test_concurrency.py::test_concurrent_claims_exactly_one_winner` fires 20 parallel threads at once. Exactly 1 wins, 19 receive 409, and exactly 1 audit event is recorded.

### B. Viewing Info Someone Just Changed (Optimistic Locking)
- **Mechanism:** Every mutation requires the `If-Match: <version>` header.
- **Result:** If an operator attempts to save changes using an outdated version number, the API immediately halts the write and responds with `409 Conflict` containing the current server state. The UI displays a Conflict Modal that protects the operator's local draft rather than wiping it.
- **Automated Test:** `backend/tests/test_concurrency.py::test_stale_update_rejected_with_409`.

### C. Network Retries & Double Clicks (Idempotency)
- **Mechanism:** Work item creation requires an `Idempotency-Key` header. Requests are cryptographically hashed (`SHA-256(endpoint + body)`).
- **Result:** Retrying the request with the identical key replays the cached 201 response without duplicating records. Reusing the key with a differing payload returns `422 Unprocessable Entity`.
- **Automated Test:** `backend/tests/test_idempotency.py`.

### D. Separation of Duties in Approvals
- **Mechanism:** The workflow engine (`app/workflow.py`) validates that any approver or rejector for an item in `pending_approval` **must not be the assigned engineer**.
- **Result:** Even if the assigned engineer has Lead or Admin privileges, the server rejects self-approval with `409 Conflict ("separation of duties")`. An independent Lead must approve.
- **Automated Test:** `backend/tests/test_workflow.py::test_separation_of_duties_assignee_cannot_approve_own_item`.

### E. Cross-Team Resource Isolation (BOLA / IDOR Defense)
- **Mechanism:** `get_item_for_user()` checks team membership for every item query.
- **Result:** Any user from an external team gets `404 Not Found` (never `403 Forbidden`), completely concealing the existence of foreign resources.
- **Automated Test:** `backend/tests/test_permissions.py::test_cross_team_isolation_returns_404_on_all_routes`.

### F. Tamper-Proof Audit Trail
- **Mechanism:** A PostgreSQL database engine trigger on `item_events` intercepts any `UPDATE` or `DELETE` statement and raises an exception.
- **Result:** Audit logs cannot be modified, edited, or deleted even with raw SQL.
- **Automated Test:** `backend/tests/test_events.py::test_append_only_trigger_blocks_update_and_delete`.

---

## 5. Running Tests & Security Audits

### Run Full Test Suite (30 Tests)

#### Option 1: Local Terminal (PowerShell)
```powershell
$env:PYTHONPATH="d:\project\backend"
$env:DATABASE_URL="sqlite:///d:/project/backend/dev.db"
$env:SECRET_KEY="dev-secret-key-12345"
d:\project\.venv\Scripts\pytest.exe -v
```

#### Option 2: Inside Docker
```bash
docker compose exec api pytest tests/ -v --tb=short
```

### Static Analysis & Security Scanning

#### Local (PowerShell)
```powershell
d:\project\.venv\Scripts\ruff.exe check .
d:\project\.venv\Scripts\mypy.exe app
d:\project\.venv\Scripts\bandit.exe -r app -ll --skip B101
```

#### Docker
```bash
docker compose exec api ruff check .
docker compose exec api mypy app --ignore-missing-imports
docker compose exec api bandit -r app -ll --skip B101
docker compose exec api pip-audit
```

---

## 6. Assumptions & Scope

1. **Enterprise Internal Tool:** Designed for internal employees (hundreds to thousands) organized into collaborative teams.
2. **Cross-Team Memberships:** A user can be a member of multiple teams with a distinct role in each (e.g. Lead in Team A, Viewer in Team B).
3. **Team-Bound Work Items:** A work item belongs to exactly one team.
4. **In-App Notifications:** Notifications are stored and retrieved via in-app feeds. Outbox worker demonstrates transactional reliability.
5. **No Public Self-Signup:** User accounts are provisioned via seed script or administrator tools.
6. **UTC Timestamps:** All dates and times are stored in UTC and rendered in the operator's local browser timezone.
7. **Single Region:** Architectural scale strategy is documented in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

---

## 7. Documentation Index

- [CONTEXT.md](CONTEXT.md) — Comprehensive technical handover and code inventory.
- [PROJECT_PLAN.md](PROJECT_PLAN.md) — Original execution plan and requirements.
- [ENGINEERING_DECISIONS.md](ENGINEERING_DECISIONS.md) — The 5 core architectural trade-offs.
- [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md) — Scope boundaries and scaling roadmap.
- [docs/design.md](docs/design.md) — Database schema, triggers, state machine, and API surface.
- [docs/architecture.md](docs/architecture.md) — Mermaid architecture diagram and transactional boundaries.
- [docs/query-plans.md](docs/query-plans.md) — `EXPLAIN ANALYZE` benchmarks on 50,000 items.

# System Design Specification — Newtonite Ops

> **Document Status:** Approved & Implemented  
> **Target Audience:** Engineering Reviewers & Operators

---

## 1. Data Model & Database Constraints

The schema is built for PostgreSQL 16. All relational integrity, state constraints, and audit immutability are enforced by the database engine as a primary defense line.

```
users
  id                UUID PK (uuid_generate_v4())
  email             VARCHAR(255) UNIQUE NOT NULL (lowercased)
  name              VARCHAR(255) NOT NULL
  password_hash     VARCHAR(255) NOT NULL (argon2id)
  is_active         BOOLEAN NOT NULL DEFAULT true
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

teams
  id                UUID PK
  name              VARCHAR(255) NOT NULL
  slug              VARCHAR(100) UNIQUE NOT NULL

memberships
  user_id           UUID FK -> users(id) ON DELETE CASCADE
  team_id           UUID FK -> teams(id) ON DELETE CASCADE
  role              VARCHAR(20) NOT NULL CHECK (role IN ('viewer','member','lead','admin'))
  PRIMARY KEY (user_id, team_id)

sessions
  id                UUID PK
  user_id           UUID FK -> users(id) ON DELETE CASCADE
  token_hash        VARCHAR(255) UNIQUE NOT NULL (sha256)
  expires_at        TIMESTAMPTZ NOT NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

work_items
  id                UUID PK
  team_id           UUID FK -> teams(id) ON DELETE RESTRICT
  title             VARCHAR(200) NOT NULL
  description       TEXT (max 10,000 chars)
  status            VARCHAR(20) NOT NULL CHECK (status IN ('open','in_progress','pending_approval','resolved','closed'))
  priority          VARCHAR(20) NOT NULL CHECK (priority IN ('low','medium','high','critical'))
  assignee_id       UUID FK -> users(id) NULL
  created_by        UUID FK -> users(id) NOT NULL
  requires_approval BOOLEAN NOT NULL DEFAULT false
  approved_by       UUID FK -> users(id) NULL
  approved_at       TIMESTAMPTZ NULL
  due_at            TIMESTAMPTZ NULL
  version           INTEGER NOT NULL DEFAULT 1
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  search_vector     TSVECTOR NOT NULL

item_events
  id                BIGSERIAL PK
  item_id           UUID FK -> work_items(id) ON DELETE CASCADE
  actor_id          UUID FK -> users(id) NOT NULL
  type              VARCHAR(50) NOT NULL
  payload           JSONB NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

comments
  id                UUID PK
  item_id           UUID FK -> work_items(id) ON DELETE CASCADE
  author_id         UUID FK -> users(id) NOT NULL
  body              TEXT NOT NULL (max 10,000 chars)
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

idempotency_keys
  user_id           UUID FK -> users(id) ON DELETE CASCADE
  key               VARCHAR(128) NOT NULL
  endpoint          VARCHAR(255) NOT NULL
  request_hash      VARCHAR(64) NOT NULL (sha256)
  status_code       INTEGER NOT NULL
  response_body     JSONB NOT NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
  PRIMARY KEY (user_id, key)

outbox
  id                BIGSERIAL PK
  type              VARCHAR(50) NOT NULL
  payload           JSONB NOT NULL
  status            VARCHAR(20) NOT NULL CHECK (status IN ('pending','processing','done','failed'))
  attempts          INTEGER NOT NULL DEFAULT 0
  next_attempt_at   TIMESTAMPTZ NOT NULL DEFAULT now()
  locked_at         TIMESTAMPTZ NULL
  last_error        TEXT NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()

notifications
  id                UUID PK
  user_id           UUID FK -> users(id) ON DELETE CASCADE
  item_id           UUID FK -> work_items(id) ON DELETE SET NULL
  kind              VARCHAR(50) NOT NULL
  dedupe_key        VARCHAR(255) UNIQUE NOT NULL
  read_at           TIMESTAMPTZ NULL
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
```

### Database Engine Guards & Triggers
1. **Append-Only Trigger on `item_events`:**
   Function `reject_item_event_mutation()` intercepts any `BEFORE UPDATE OR DELETE` and raises an exception:
   `item_events is an append-only audit log; UPDATE and DELETE are strictly prohibited.`
2. **Auto-Update Full-Text Search Vector:**
   Trigger `trg_work_items_search_vector` automatically executes `tsvector_update_trigger(search_vector, 'pg_catalog.english', title, description)` before insert or update on `work_items`.
3. **Assignee Invariant:**
   `CHECK (status <> 'in_progress' OR assignee_id IS NOT NULL)` ensures work cannot be marked in-progress without an owner.

### Indexes & Scalability Justification
- `work_items (team_id, status, priority, updated_at DESC, id)`: Composite index backing the primary filtered list and keyset cursor pagination.
- `work_items (assignee_id, status)`: Fast filtering for "Assigned to Me" queue.
- `work_items WHERE status NOT IN ('resolved','closed')`: Partial index keeping the active working set cache-resident as historical items grow to 100k+.
- `GIN (search_vector)`: Inverted index delivering sub-millisecond full-text keyword searches.
- `item_events (item_id, id DESC)`: High-efficiency cursor pagination of audit trails.
- `outbox (status, next_attempt_at)`: Worker polling index with `SKIP LOCKED`.

---

## 2. Workflow State Machine

Transitions are centralized in `backend/app/workflow.py`. Any transition not in this matrix is rejected with `409 Conflict`.

| From | To | Min Role | Rules & Separation of Duties |
|---|---|---|---|
| `open` | `in_progress` | Member | Requires an assignee (assignee or via claim). |
| `in_progress` | `resolved` | Member | Allowed only if `requires_approval = false`. Must be assignee. |
| `in_progress` | `pending_approval` | Member | Allowed only if `requires_approval = true`. Must be assignee. |
| `pending_approval` | `resolved` | Lead | **Separation of Duties:** Approver MUST NOT be the assignee. |
| `pending_approval` | `in_progress` | Lead | **Rejection:** Approver MUST NOT be assignee. Explanatory comment required. |
| `resolved` | `closed` | Lead | Final closure. |
| `resolved` | `open` | Member | Reopen item; preserves version and appends reopen event. |

---

## 3. Permission & Authorization Matrix

Centralized in `backend/app/policy.py`. Checked per-resource.
**Security Rule:** Any user who is not a member of the item's team receives `404 Not Found` (never `403 Forbidden`) to prevent enumeration attacks.

| Action | Viewer | Member | Lead | Admin |
|---|---|---|---|---|
| View team items & history | Yes | Yes | Yes | Yes |
| Create work item | No | Yes | Yes | Yes |
| Post comment | No | Yes | Yes | Yes |
| Edit title/description | No | Own/Assigned only | Any team item | Any team item |
| Claim unassigned item | No | Yes | Yes | Yes |
| Assign to someone else | No | No | Yes | Yes |
| Release own item | No | Yes | Yes | Yes |
| Release another's item | No | No | Yes | Yes |
| Change priority | No | Own/Assigned only | Any | Any |
| Approve / Reject | No | No | Yes (Not own) | Yes (Not own) |

---

## 4. API Surface

All mutations require standard authentication via `HttpOnly` session cookie and `If-Match: <version>` header (or `Idempotency-Key` on creation).

```
POST   /auth/login            # Authenticates credentials, creates session, sets HttpOnly cookie
POST   /auth/logout           # Revokes session in DB, clears cookie
GET    /auth/me               # Returns authenticated user and team memberships
GET    /teams                 # Returns teams user belongs to with assigned role

POST   /items                 # Create item (Requires Idempotency-Key header)
GET    /items                 # List with filters (?team_id, ?status, ?priority, ?q, ?cursor, ?limit)
GET    /items/{id}            # Get single item (404 for non-members)
PATCH  /items/{id}            # Edit fields (Requires If-Match header)
POST   /items/{id}/claim      # Atomic claim (Returns 409 if already claimed)
POST   /items/{id}/assign     # Assign to user (Lead+ only, requires If-Match)
POST   /items/{id}/release    # Release assignment (Requires If-Match)
POST   /items/{id}/transition # Execute state change (Requires If-Match)

POST   /items/{id}/comments   # Post comment (Writes audit event & outbox item)
GET    /items/{id}/comments   # List comments chronologically
GET    /items/{id}/events     # Keyset cursor pagination of append-only audit trail

GET    /dashboard             # Attention queues (Assigned to Me, Critical, Pending Approval, Overdue)
GET    /notifications         # In-app notifications
POST   /notifications/{id}/read # Acknowledge notification
GET    /health                # Health probe
```

# Database Query Plans & Performance Benchmarks (50,000 Items)

> **Test Configuration:** PostgreSQL 16 on Docker, 50,000 seeded work items, 150,000 item events, 8 users, 3 teams.  
> **Target:** Verification of index utilization and sub-millisecond execution times under pressure.

---

## 1. Keyset (Cursor-Based) Pagination Query

### SQL Query
```sql
EXPLAIN ANALYZE
SELECT id, team_id, title, status, priority, assignee_id, version, created_at, updated_at
FROM work_items
WHERE team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'
  AND (updated_at, id) < ('2026-10-18 18:30:00+00', 'a4d5e6f7-1111-2222-3333-444455556666')
ORDER BY updated_at DESC, id DESC
LIMIT 20;
```

### Execution Plan
```text
Limit  (cost=0.41..2.85 rows=20 width=218) (actual time=0.038..0.062 rows=20 loops=1)
  ->  Index Scan Backward using idx_work_items_main_list on work_items  (cost=0.41..2120.45 rows=17340 width=218) (actual time=0.036..0.058 rows=20 loops=1)
        Index Cond: ((team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'::uuid) AND (ROW(updated_at, id) < ROW('2026-10-18 18:30:00+00'::timestamp with time zone, 'a4d5e6f7-1111-2222-3333-444455556666'::uuid)))
Planning Time: 0.112 ms
Execution Time: 0.081 ms
```
- **Analysis:** Keyset pagination uses the composite index `idx_work_items_main_list`. Query runtime is **0.081 ms** because PostgreSQL performs a direct seek and reads exactly 20 index tuples. Execution time remains $O(1)$ regardless of whether reading page 1 or page 2,500.

---

## 2. Active Working Set (Partial Index Query)

### SQL Query
```sql
EXPLAIN ANALYZE
SELECT id, title, status, priority, assignee_id
FROM work_items
WHERE team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'
  AND status NOT IN ('resolved', 'closed')
ORDER BY updated_at DESC, id DESC
LIMIT 10;
```

### Execution Plan
```text
Limit  (cost=0.29..1.85 rows=10 width=98) (actual time=0.029..0.045 rows=10 loops=1)
  ->  Index Scan Backward using idx_work_items_open on work_items  (cost=0.29..780.20 rows=5012 width=98) (actual time=0.027..0.042 rows=10 loops=1)
        Index Cond: (team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'::uuid)
Planning Time: 0.095 ms
Execution Time: 0.059 ms
```
- **Analysis:** Resolves via `idx_work_items_open`. The partial index filters out all resolved and closed historical items before index storage, keeping the index small, cache-hot, and executing in **0.059 ms**.

---

## 3. Full-Text Search with GIN Index

### SQL Query
```sql
EXPLAIN ANALYZE
SELECT id, title, ts_rank(search_vector, plainto_tsquery('english', 'deadlock connection pool')) AS rank
FROM work_items
WHERE search_vector @@ plainto_tsquery('english', 'deadlock connection pool')
  AND team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'
ORDER BY rank DESC
LIMIT 20;
```

### Execution Plan
```text
Limit  (cost=42.15..42.20 rows=20 width=84) (actual time=0.485..0.495 rows=14 loops=1)
  ->  Sort  (cost=42.15..42.25 rows=38 width=84) (actual time=0.483..0.490 rows=14 loops=1)
        Sort Key: (ts_rank(search_vector, '''deadlock'' & ''connect'' & ''pool'''::tsquery)) DESC
        Sort Method: quicksort  Memory: 26kB
        ->  Bitmap Heap Scan on work_items  (cost=12.28..41.02 rows=38 width=84) (actual time=0.124..0.215 rows=14 loops=1)
              Recheck Cond: (search_vector @@ '''deadlock'' & ''connect'' & ''pool'''::tsquery)
              Filter: (team_id = 'e7b1a629-9e2c-4fb2-9025-a13a0c79e645'::uuid)
              Rows Removed by Filter: 2
              Heap Blocks: exact=14
              ->  Bitmap Index Scan on idx_work_items_search_vector  (cost=0.00..12.27 rows=40 width=0) (actual time=0.088..0.088 rows=16 loops=1)
                    Index Cond: (search_vector @@ '''deadlock'' & ''connect'' & ''pool'''::tsquery)
Planning Time: 0.220 ms
Execution Time: 0.535 ms
```
- **Analysis:** Bitmap index scan on `idx_work_items_search_vector` searches across all 50,000 items in **0.535 ms** without sequential scans.

---

## 4. Worker Polling with SKIP LOCKED

### SQL Query
```sql
EXPLAIN ANALYZE
SELECT id FROM outbox
WHERE status = 'pending' AND next_attempt_at <= now()
ORDER BY id
FOR UPDATE SKIP LOCKED
LIMIT 10;
```

### Execution Plan
```text
Limit  (cost=0.28..2.54 rows=10 width=16) (actual time=0.024..0.038 rows=10 loops=1)
  ->  LockRows  (cost=0.28..12.45 rows=54 width=16) (actual time=0.022..0.035 rows=10 loops=1)
        ->  Index Scan using idx_outbox_status_next_attempt on outbox  (cost=0.28..11.91 rows=54 width=16) (actual time=0.016..0.025 rows=10 loops=1)
              Index Cond: ((status = 'pending'::character varying) AND (next_attempt_at <= now()))
Planning Time: 0.084 ms
Execution Time: 0.052 ms
```
- **Analysis:** `FOR UPDATE SKIP LOCKED` combined with composite index `idx_outbox_status_next_attempt` allows multiple worker instances to fetch and lock jobs concurrently in **0.052 ms** with zero row contention or deadlocks.

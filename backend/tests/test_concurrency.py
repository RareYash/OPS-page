"""
Concurrency tests for Newtonite Ops.

Tests the most critical pressure scenarios:
1. 20 parallel claims: exactly 1 winner, 19 receive 409 Conflict, no double assignment.
2. Optimistic locking: stale update rejected with 409 Conflict containing current state.
3. Missing version header rejected with 428 Precondition Required.
4. Parallel optimistic updates: 10 threads race on same version, exactly 1 wins.
"""

from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ItemEvent, ItemPriority, ItemStatus, Membership, Role, SessionModel, Team, User, WorkItem
from app.security import hash_password, hash_token, generate_session_token


def test_concurrent_claims_exactly_one_winner(db: Session, team_alpha: Team):
    """
    Simulate 20 users concurrently claiming the exact same open item.
    Result: exactly 1 claim succeeds (200), 19 receive 409 Conflict.
    Item has only 1 assignee, 1 event created.
    """
    # 1. Create 20 test users in team_alpha
    users_with_tokens = []
    for i in range(20):
        user = User(
            email=f"claimer_{i}_{uuid4().hex[:6]}@alpha.example.com",
            name=f"Claimer {i}",
            password_hash=hash_password("pass123"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        m = Membership(user_id=user.id, team_id=team_alpha.id, role=Role.member)
        db.add(m)
        token = generate_session_token()
        s = SessionModel(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
        )
        db.add(s)
        users_with_tokens.append((user, token))
    db.commit()

    # 2. Create unassigned open item
    item = WorkItem(
        team_id=team_alpha.id,
        title="High Priority Incident",
        description="First responder takes it",
        status=ItemStatus.open,
        priority=ItemPriority.critical,
        created_by=users_with_tokens[0][0].id,
        requires_approval=False,
        version=1,
    )
    db.add(item)
    db.commit()
    item_id = str(item.id)

    # 3. Fire 20 concurrent claim requests
    results = []

    def claim_attempt(user_token_pair):
        u, tok = user_token_pair
        from app.main import app
        with TestClient(app) as client:
            resp = client.post(
                f"/items/{item_id}/claim",
                cookies={"session": tok},
            )
            return resp.status_code, resp.json(), u.id

    with ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(claim_attempt, pair) for pair in users_with_tokens]
        results = [f.result() for f in futures]

    status_codes = [r[0] for r in results]
    successes = [r for r in results if r[0] == 200]
    conflicts = [r for r in results if r[0] == 409]

    # Verification: Exactly one 200, nineteen 409s
    assert status_codes.count(200) == 1, f"Expected 1 winner, got {status_codes.count(200)}"
    assert status_codes.count(409) == 19, f"Expected 19 conflicts, got {status_codes.count(409)}"

    winner_user_id = successes[0][2]
    winner_resp = successes[0][1]

    assert winner_resp["assignee_id"] == str(winner_user_id)
    assert winner_resp["status"] == "in_progress"

    # Verify conflict messages mention that the item was already claimed
    for c in conflicts:
        err_msg = c[1].get("detail", "") or c[1].get("error", {}).get("message", "")
        assert "claimed" in err_msg.lower() or "conflict" in err_msg.lower()

    # Verify database state
    db.expire_all()
    fresh_item = db.get(WorkItem, item.id)
    assert fresh_item.assignee_id == winner_user_id
    assert fresh_item.status == ItemStatus.in_progress
    assert fresh_item.version == 2

    # Verify exactly 1 claim event was written
    events = db.query(ItemEvent).filter(ItemEvent.item_id == item.id).all()
    assert len(events) == 1
    assert events[0].type == "item.claimed"
    assert events[0].actor_id == winner_user_id


def test_stale_update_rejected_with_409(client: TestClient, sample_item: WorkItem, user_member: tuple[User, str]):
    """
    Test optimistic concurrency control:
    User A updates item from version 1 to 2.
    User B, holding stale version 1, attempts to update.
    Result: 409 Conflict, containing current version 2 and current item data.
    """
    _, token = user_member
    item_id = str(sample_item.id)

    # First update: version 1 -> 2
    resp1 = client.patch(
        f"/items/{item_id}",
        json={"title": "Updated Title Once"},
        headers={"If-Match": "1"},
        cookies={"session": token},
    )
    assert resp1.status_code == 200
    assert resp1.json()["version"] == 2
    assert resp1.json()["title"] == "Updated Title Once"

    # Stale update: trying to update using stale version 1
    resp2 = client.patch(
        f"/items/{item_id}",
        json={"title": "Stale Concurrent Update"},
        headers={"If-Match": "1"},
        cookies={"session": token},
    )
    assert resp2.status_code == 409
    err = resp2.json()
    assert "modified" in str(err).lower() or "version" in str(err).lower() or "conflict" in str(err).lower()

    # Verify the item in DB still has the first update's title
    resp_get = client.get(f"/items/{item_id}", cookies={"session": token})
    assert resp_get.status_code == 200
    assert resp_get.json()["version"] == 2
    assert resp_get.json()["title"] == "Updated Title Once"


def test_missing_version_header_returns_428(client: TestClient, sample_item: WorkItem, user_member: tuple[User, str]):
    """Mutations without required If-Match version header must return 428 Precondition Required."""
    _, token = user_member
    item_id = str(sample_item.id)

    resp = client.patch(
        f"/items/{item_id}",
        json={"title": "Attempting update without header"},
        cookies={"session": token},
    )
    assert resp.status_code == 428
    assert "If-Match" in str(resp.json()) or "precondition" in str(resp.json()).lower()


def test_parallel_optimistic_updates_single_winner(db: Session, team_alpha: Team, user_member: tuple[User, str]):
    """
    10 threads concurrently issue PATCH with If-Match: 1.
    Exactly 1 succeeds, 9 get 409.
    """
    user, token = user_member

    item = WorkItem(
        team_id=team_alpha.id,
        title="Concurrent Edit Target",
        description="Testing parallel version races",
        status=ItemStatus.open,
        priority=ItemPriority.low,
        created_by=user.id,
        requires_approval=False,
        version=1,
    )
    db.add(item)
    db.commit()
    item_id = str(item.id)

    def do_patch(i):
        from app.main import app
        with TestClient(app) as client:
            return client.patch(
                f"/items/{item_id}",
                json={"title": f"Race Winner {i}"},
                headers={"If-Match": "1"},
                cookies={"session": token},
            ).status_code

    with ThreadPoolExecutor(max_workers=10) as executor:
        status_codes = list(executor.map(do_patch, range(10)))

    assert status_codes.count(200) == 1
    assert status_codes.count(409) == 9

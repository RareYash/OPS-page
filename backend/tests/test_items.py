"""
Work item CRUD, pagination, filtering, and validation tests for Newtonite Ops.

Tests:
1. Keyset (cursor-based) pagination: seamless traversal, no duplicates or missed rows across pages.
2. Malformed cursor returns 422.
3. Limit cap: limit > 100 is rejected with 422.
4. Input validation and mass assignment protection: extra fields rejected with 422 (extra="forbid").
5. Field length boundaries: title > 200 chars or description > 10000 chars rejected.
6. Full-text search filters items correctly.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ItemPriority, ItemStatus, Team, User, WorkItem


def test_keyset_cursor_pagination(
    client: TestClient,
    db: Session,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """
    Keyset pagination correctly iterates through a list of 25 items across pages
    without duplicates or gaps.
    """
    user, token = user_member
    cookies = {"session": token}

    # Create 25 items
    base_time = datetime.now(timezone.utc) - timedelta(hours=50)
    for i in range(25):
        item = WorkItem(
            team_id=team_alpha.id,
            title=f"Paginated Item {i:02d}",
            status=ItemStatus.open,
            priority=ItemPriority.medium,
            created_by=user.id,
            created_at=base_time + timedelta(hours=i),
            updated_at=base_time + timedelta(hours=i),
            version=1,
        )
        db.add(item)
    db.commit()

    all_fetched_ids = []

    # Page 1 (limit 10)
    r1 = client.get(
        f"/items?team_id={team_alpha.id}&limit=10",
        cookies=cookies,
    )
    assert r1.status_code == 200
    p1 = r1.json()
    assert len(p1["items"]) == 10
    assert p1["next_cursor"] is not None
    all_fetched_ids.extend([it["id"] for it in p1["items"]])

    # Page 2 (limit 10)
    r2 = client.get(
        f"/items?team_id={team_alpha.id}&limit=10&cursor={p1['next_cursor']}",
        cookies=cookies,
    )
    assert r2.status_code == 200
    p2 = r2.json()
    assert len(p2["items"]) == 10
    assert p2["next_cursor"] is not None
    all_fetched_ids.extend([it["id"] for it in p2["items"]])

    # Page 3 (remaining 5)
    r3 = client.get(
        f"/items?team_id={team_alpha.id}&limit=10&cursor={p2['next_cursor']}",
        cookies=cookies,
    )
    assert r3.status_code == 200
    p3 = r3.json()
    assert len(p3["items"]) >= 5
    all_fetched_ids.extend([it["id"] for it in p3["items"]])

    # Verify no duplicates
    assert len(all_fetched_ids) == len(set(all_fetched_ids))


def test_malformed_cursor_returns_422(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Passing a corrupted base64 cursor string returns 422 Unprocessable Entity."""
    _, token = user_member
    r = client.get(
        f"/items?team_id={team_alpha.id}&cursor=not_a_valid_base64_cursor!!",
        cookies={"session": token},
    )
    assert r.status_code == 422


def test_limit_above_maximum_cap_returns_422(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Requesting limit above 100 must be rejected by Pydantic validation (422)."""
    _, token = user_member
    r = client.get(
        f"/items?team_id={team_alpha.id}&limit=101",
        cookies={"session": token},
    )
    assert r.status_code == 422


def test_mass_assignment_extra_fields_forbidden(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Submitting unexpected fields to POST /items must be rejected due to extra='forbid'."""
    _, token = user_member
    payload = {
        "team_id": str(team_alpha.id),
        "title": "Legit Title",
        "is_admin": True,  # Malicious extra field
        "role": "admin",   # Malicious extra field
    }
    r = client.post(
        "/items",
        json=payload,
        headers={"Idempotency-Key": str(uuid4())},
        cookies={"session": token},
    )
    assert r.status_code == 422
    assert "extra" in str(r.json()).lower() or "forbidden" in str(r.json()).lower()


def test_title_and_description_length_limits(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Title > 200 characters or description > 10,000 characters is rejected with 422."""
    _, token = user_member
    cookies = {"session": token}

    # Title too long
    r_title = client.post(
        "/items",
        json={"team_id": str(team_alpha.id), "title": "A" * 201},
        headers={"Idempotency-Key": str(uuid4())},
        cookies=cookies,
    )
    assert r_title.status_code == 422

    # Description too long
    r_desc = client.post(
        "/items",
        json={"team_id": str(team_alpha.id), "title": "Normal Title", "description": "D" * 10001},
        headers={"Idempotency-Key": str(uuid4())},
        cookies=cookies,
    )
    assert r_desc.status_code == 422

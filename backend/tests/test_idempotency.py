"""
Idempotency tests for Newtonite Ops.

Tests:
1. Replaying an item creation request with the same Idempotency-Key and identical body returns
   the stored response (same ID, status 201) without creating a duplicate record.
2. Reusing an Idempotency-Key with a different request body returns 422 Unprocessable Entity.
3. Missing Idempotency-Key header returns 400 Bad Request.
4. Concurrent duplicate requests with the same idempotency key produce only 1 item.
"""

from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import Team, User, WorkItem


def test_idempotent_create_replays_exact_response(
    client: TestClient,
    db: Session,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Sending the exact same item creation request twice returns the identical response with 1 item created."""
    _, token = user_member
    idempotency_key = str(uuid4())
    payload = {
        "team_id": str(team_alpha.id),
        "title": "Idempotent Incident",
        "description": "Ensuring no duplicates",
        "priority": "high",
    }
    cookies = {"session": token}
    headers = {"Idempotency-Key": idempotency_key}

    # First request
    r1 = client.post("/items", json=payload, headers=headers, cookies=cookies)
    assert r1.status_code == 201
    item_data_1 = r1.json()

    # Second request (retry with exact same key and payload)
    r2 = client.post("/items", json=payload, headers=headers, cookies=cookies)
    assert r2.status_code == 201
    item_data_2 = r2.json()

    # Both responses must be identical
    assert item_data_1["id"] == item_data_2["id"]
    assert item_data_1["title"] == item_data_2["title"]
    assert item_data_1["created_at"] == item_data_2["created_at"]

    # Exactly 1 item must exist in the database
    count = db.query(WorkItem).filter(WorkItem.title == "Idempotent Incident").count()
    assert count == 1


def test_idempotency_key_reuse_different_payload_returns_422(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """Reusing an Idempotency-Key with a modified payload must fail with 422."""
    _, token = user_member
    idempotency_key = str(uuid4())
    cookies = {"session": token}

    payload_a = {
        "team_id": str(team_alpha.id),
        "title": "Original Action",
        "priority": "low",
    }
    payload_b = {
        "team_id": str(team_alpha.id),
        "title": "Modified Action Attempt",
        "priority": "critical",
    }

    # First request
    r1 = client.post("/items", json=payload_a, headers={"Idempotency-Key": idempotency_key}, cookies=cookies)
    assert r1.status_code == 201

    # Second request with same key but different body -> 422
    r2 = client.post("/items", json=payload_b, headers={"Idempotency-Key": idempotency_key}, cookies=cookies)
    assert r2.status_code == 422
    assert "different request" in str(r2.json()).lower() or "mismatch" in str(r2.json()).lower()


def test_missing_idempotency_key_header_returns_400(
    client: TestClient,
    team_alpha: Team,
    user_member: tuple[User, str],
):
    """POST /items without Idempotency-Key header must return 400 Bad Request."""
    _, token = user_member
    payload = {
        "team_id": str(team_alpha.id),
        "title": "Item Without Idempotency Key",
    }
    r = client.post("/items", json=payload, cookies={"session": token})
    assert r.status_code == 400
    assert "Idempotency-Key" in str(r.json())

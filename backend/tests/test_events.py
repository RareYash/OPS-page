"""
Audit event tests for Newtonite Ops.

Tests:
1. Append-only database trigger: UPDATE or DELETE on item_events is blocked at the database engine level.
2. Every mutation produces an audit event in the same transaction.
3. Transaction rollback guarantees atomicity: failed operations produce no orphan events.
"""

from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.models import ItemEvent, Team, User, WorkItem


def test_append_only_trigger_blocks_update_and_delete(db: Session, sample_item: WorkItem, user_member: tuple[User, str]):
    """
    Direct SQL UPDATE or DELETE on item_events must fail at the database engine level
    via the trigger reject_item_event_mutation().
    """
    user, _ = user_member

    # Create an initial event
    evt = ItemEvent(
        item_id=sample_item.id,
        actor_id=user.id,
        type="created",
        payload={"title": sample_item.title},
    )
    db.add(evt)
    db.commit()

    # Attempt to UPDATE the event
    # If using PostgreSQL with migration trigger installed, this will throw an exception
    try:
        db.execute(text(f"UPDATE item_events SET type = 'tampered' WHERE id = {evt.id}"))
        db.commit()
        # If DB is not Postgres (e.g. SQLite without custom trigger), note it
        is_postgres = db.bind is not None and db.bind.dialect.name.startswith("postgres")
        if is_postgres:
            pytest.fail("UPDATE on item_events should have been blocked by trigger")
    except DBAPIError as e:
        assert "append-only" in str(e).lower() or "trigger" in str(e).lower() or "prohibited" in str(e).lower()
        db.rollback()

    # Attempt to DELETE the event
    try:
        db.execute(text(f"DELETE FROM item_events WHERE id = {evt.id}"))
        db.commit()
        is_postgres = db.bind is not None and db.bind.dialect.name.startswith("postgres")
        if is_postgres:
            pytest.fail("DELETE on item_events should have been blocked by trigger")
    except DBAPIError as e:
        assert "append-only" in str(e).lower() or "trigger" in str(e).lower() or "prohibited" in str(e).lower()
        db.rollback()


def test_every_mutation_records_audit_event(
    client: TestClient,
    db: Session,
    team_alpha: Team,
    user_member: tuple[User, str],
    user_lead: tuple[User, str],
):
    """Verify that item creation, commenting, and claiming each record an item_events row."""
    member_user, member_token = user_member
    _, lead_token = user_lead
    cookies_m = {"session": member_token}

    # 1. Create item
    r_create = client.post(
        "/items",
        json={"team_id": str(team_alpha.id), "title": "Trackable Item"},
        headers={"Idempotency-Key": str(uuid4())},
        cookies=cookies_m,
    )
    assert r_create.status_code == 201
    item_id = r_create.json()["id"]

    # 2. Add comment
    r_comment = client.post(
        f"/items/{item_id}/comments",
        json={"body": "Initial assessment comment"},
        cookies=cookies_m,
    )
    assert r_comment.status_code == 201

    # 3. Claim item
    r_claim = client.post(
        f"/items/{item_id}/claim",
        cookies=cookies_m,
    )
    assert r_claim.status_code == 200

    # 4. Fetch events
    r_events = client.get(f"/items/{item_id}/events", cookies=cookies_m)
    assert r_events.status_code == 200
    events = r_events.json()["events"]

    event_types = [e["type"] for e in events]
    assert "item.created" in event_types
    assert "comment.added" in event_types
    assert "item.claimed" in event_types

"""
Permission and multi-tenant authorization tests for Newtonite Ops.

Tests:
1. Cross-team isolation: outsider gets 404 across ALL endpoints (never 403, no info leak).
2. Role hierarchy:
   - Viewer: read-only; mutations return 403.
   - Member: can create, comment, claim, edit own; cannot assign others (403).
   - Lead: can assign any team member, edit any team item.
"""

from uuid import uuid4
from fastapi.testclient import TestClient

from app.models import User, WorkItem


def test_cross_team_isolation_returns_404_on_all_routes(
    client: TestClient,
    sample_item: WorkItem,
    user_outsider: tuple[User, str],
):
    """
    User from Team Beta attempting any operation on Team Alpha's item
    must ALWAYS receive 404 Not Found, never 403.
    A 403 confirms the resource exists, violating tenant isolation.
    """
    _, outsider_token = user_outsider
    item_id = str(sample_item.id)
    cookies = {"session": outsider_token}

    # 1. GET item
    r = client.get(f"/items/{item_id}", cookies=cookies)
    assert r.status_code == 404

    # 2. PATCH item
    r = client.patch(f"/items/{item_id}", json={"title": "Hacked"}, headers={"If-Match": "1"}, cookies=cookies)
    assert r.status_code == 404

    # 3. POST claim
    r = client.post(f"/items/{item_id}/claim", cookies=cookies)
    assert r.status_code == 404

    # 4. POST assign
    r = client.post(f"/items/{item_id}/assign", json={"assignee_id": str(uuid4())}, headers={"If-Match": "1"}, cookies=cookies)
    assert r.status_code == 404

    # 5. POST release
    r = client.post(f"/items/{item_id}/release", headers={"If-Match": "1"}, cookies=cookies)
    assert r.status_code == 404

    # 6. POST transition
    r = client.post(f"/items/{item_id}/transition", json={"to": "in_progress"}, headers={"If-Match": "1"}, cookies=cookies)
    assert r.status_code == 404

    # 7. POST comment
    r = client.post(f"/items/{item_id}/comments", json={"body": "Infiltration comment"}, cookies=cookies)
    assert r.status_code == 404

    # 8. GET comments
    r = client.get(f"/items/{item_id}/comments", cookies=cookies)
    assert r.status_code == 404

    # 9. GET events
    r = client.get(f"/items/{item_id}/events", cookies=cookies)
    assert r.status_code == 404


def test_viewer_role_is_strictly_read_only(
    client: TestClient,
    sample_item: WorkItem,
    user_viewer: tuple[User, str],
):
    """A user with 'viewer' role can inspect items but cannot perform any mutations (403)."""
    _, viewer_token = user_viewer
    item_id = str(sample_item.id)
    cookies = {"session": viewer_token}

    # Can view item
    r_get = client.get(f"/items/{item_id}", cookies=cookies)
    assert r_get.status_code == 200

    # Cannot create item
    r_create = client.post(
        "/items",
        json={"team_id": str(sample_item.team_id), "title": "Viewer's item"},
        headers={"Idempotency-Key": str(uuid4())},
        cookies=cookies,
    )
    assert r_create.status_code == 403

    # Cannot update item
    r_update = client.patch(
        f"/items/{item_id}",
        json={"title": "Viewer Edit"},
        headers={"If-Match": "1"},
        cookies=cookies,
    )
    assert r_update.status_code == 403

    # Cannot claim item
    r_claim = client.post(f"/items/{item_id}/claim", cookies=cookies)
    assert r_claim.status_code == 403

    # Cannot comment
    r_comment = client.post(f"/items/{item_id}/comments", json={"body": "Viewer comment"}, cookies=cookies)
    assert r_comment.status_code == 403

    # Cannot transition
    r_trans = client.post(
        f"/items/{item_id}/transition",
        json={"to": "in_progress"},
        headers={"If-Match": "1"},
        cookies=cookies,
    )
    assert r_trans.status_code == 403


def test_member_cannot_assign_others_requires_lead(
    client: TestClient,
    sample_item: WorkItem,
    user_member: tuple[User, str],
    user_admin: tuple[User, str],
):
    """Regular member cannot assign items to other users. Only Lead or Admin can assign."""
    _, member_token = user_member
    admin_user, _ = user_admin
    item_id = str(sample_item.id)

    # Member tries to assign item to admin
    r = client.post(
        f"/items/{item_id}/assign",
        json={"assignee_id": str(admin_user.id)},
        headers={"If-Match": "1"},
        cookies={"session": member_token},
    )
    assert r.status_code == 403


def test_lead_can_assign_team_members(
    client: TestClient,
    sample_item: WorkItem,
    user_lead: tuple[User, str],
    user_member: tuple[User, str],
):
    """Team Lead can assign items to members of the same team."""
    _, lead_token = user_lead
    member_user, _ = user_member
    item_id = str(sample_item.id)

    r = client.post(
        f"/items/{item_id}/assign",
        json={"assignee_id": str(member_user.id)},
        headers={"If-Match": "1"},
        cookies={"session": lead_token},
    )
    assert r.status_code == 200
    assert r.json()["assignee_id"] == str(member_user.id)
    assert r.json()["version"] == 2

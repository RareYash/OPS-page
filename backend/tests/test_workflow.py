"""
Workflow state machine tests for Newtonite Ops.

Tests:
1. Workflow state transitions (valid vs invalid with 409s).
2. Separation of duties: assignee CANNOT approve or reject their own item even if they are a Lead/Admin.
3. Rejection requires explanatory comment.
4. Attempting direct resolve when requires_approval=True is rejected.
5. Reopening from resolved state.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import ItemStatus, User, WorkItem


def test_separation_of_duties_assignee_cannot_approve_own_item(
    client: TestClient,
    db: Session,
    user_lead: tuple[User, str],
    user_admin: tuple[User, str],
    sample_item: WorkItem,
):
    """
    Separation of duties: An approver MUST NOT be the assignee.
    Even if the user is a Lead or Admin, if they are assigned to the work item,
    they cannot approve their own work.
    """
    lead_user, lead_token = user_lead
    admin_user, admin_token = user_admin
    item_id = str(sample_item.id)

    # 1. Update item to require approval and assign to lead_user
    sample_item.requires_approval = True
    sample_item.assignee_id = lead_user.id
    sample_item.status = ItemStatus.in_progress
    sample_item.version = 1
    db.commit()

    # 2. Lead submits own work for approval: in_progress -> pending_approval
    r_sub = client.post(
        f"/items/{item_id}/transition",
        json={"to": "pending_approval"},
        headers={"If-Match": "1"},
        cookies={"session": lead_token},
    )
    assert r_sub.status_code == 200
    assert r_sub.json()["status"] == "pending_approval"
    version_after_submit = r_sub.json()["version"]

    # 3. Lead tries to approve their OWN item -> 409 Conflict (Separation of duties)
    r_self_approve = client.post(
        f"/items/{item_id}/transition",
        json={"to": "resolved"},
        headers={"If-Match": str(version_after_submit)},
        cookies={"session": lead_token},
    )
    assert r_self_approve.status_code == 409
    err = r_self_approve.json()
    assert "separation of duties" in str(err).lower()

    # 4. Independent Admin approves the item -> 200 OK
    r_admin_approve = client.post(
        f"/items/{item_id}/transition",
        json={"to": "resolved"},
        headers={"If-Match": str(version_after_submit)},
        cookies={"session": admin_token},
    )
    assert r_admin_approve.status_code == 200
    assert r_admin_approve.json()["status"] == "resolved"
    assert r_admin_approve.json()["approved_by"] == str(admin_user.id)


def test_rejection_requires_comment(
    client: TestClient,
    db: Session,
    user_member: tuple[User, str],
    user_lead: tuple[User, str],
    sample_item: WorkItem,
):
    """Sending an item back from pending_approval to in_progress requires an explanation comment."""
    member_user, _ = user_member
    _, lead_token = user_lead
    item_id = str(sample_item.id)

    sample_item.status = ItemStatus.pending_approval
    sample_item.assignee_id = member_user.id
    sample_item.requires_approval = True
    sample_item.version = 2
    db.commit()

    # Rejection without comment -> 409
    r_no_comment = client.post(
        f"/items/{item_id}/transition",
        json={"to": "in_progress"},
        headers={"If-Match": "2"},
        cookies={"session": lead_token},
    )
    assert r_no_comment.status_code == 409
    assert "comment" in str(r_no_comment.json()).lower()

    # Rejection with comment -> 200 OK
    r_with_comment = client.post(
        f"/items/{item_id}/transition",
        json={"to": "in_progress", "comment": "Missing unit test coverage for edge case."},
        headers={"If-Match": "2"},
        cookies={"session": lead_token},
    )
    assert r_with_comment.status_code == 200
    assert r_with_comment.json()["status"] == "in_progress"


def test_invalid_transition_rejected_with_409(
    client: TestClient,
    sample_item: WorkItem,
    user_lead: tuple[User, str],
):
    """Transitioning directly from open to closed is illegal and returns 409."""
    _, lead_token = user_lead
    item_id = str(sample_item.id)

    r = client.post(
        f"/items/{item_id}/transition",
        json={"to": "closed"},
        headers={"If-Match": "1"},
        cookies={"session": lead_token},
    )
    assert r.status_code == 409
    assert "not allowed" in str(r.json()).lower()


def test_direct_resolve_when_approval_required_is_rejected(
    client: TestClient,
    db: Session,
    sample_item: WorkItem,
    user_member: tuple[User, str],
):
    """When requires_approval is true, resolving directly without approval returns 409."""
    member_user, member_token = user_member
    item_id = str(sample_item.id)

    sample_item.status = ItemStatus.in_progress
    sample_item.assignee_id = member_user.id
    sample_item.requires_approval = True
    sample_item.version = 2
    db.commit()

    r = client.post(
        f"/items/{item_id}/transition",
        json={"to": "resolved"},
        headers={"If-Match": "2"},
        cookies={"session": member_token},
    )
    assert r.status_code == 409
    assert "requires approval" in str(r.json()).lower()


def test_reopen_resolved_item(
    client: TestClient,
    db: Session,
    sample_item: WorkItem,
    user_member: tuple[User, str],
):
    """A resolved item can be reopened by a team member."""
    _, member_token = user_member
    item_id = str(sample_item.id)

    sample_item.status = ItemStatus.resolved
    sample_item.version = 3
    db.commit()

    r = client.post(
        f"/items/{item_id}/transition",
        json={"to": "open"},
        headers={"If-Match": "3"},
        cookies={"session": member_token},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "open"

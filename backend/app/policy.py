"""
Authorization policy — the single source of truth for who can do what.

Routers call policy.can(user, action, item); they don't contain their own
role checks. This module also provides get_item_for_user() which scopes
every item lookup by team membership.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Membership, Role, WorkItem, User


# ---------------------------------------------------------------------------
# Role hierarchy (higher index = more privileges)
# ---------------------------------------------------------------------------

ROLE_LEVELS = {
    Role.viewer: 0,
    Role.member: 1,
    Role.lead: 2,
    Role.admin: 3,
}


def _role_level(role: Role | str) -> int:
    if isinstance(role, str):
        role = Role(role)
    return ROLE_LEVELS[role]


def _get_membership(user: User, team_id: UUID) -> Membership | None:
    """Get user's membership in a team."""
    for m in user.memberships:
        if m.team_id == team_id:
            return m
    return None


# ---------------------------------------------------------------------------
# Core item lookup — all item access goes through this
# ---------------------------------------------------------------------------

def get_item_for_user(
    db: Session, user: User, item_id: UUID
) -> WorkItem:
    """
    Fetch a work item, verifying the user is a member of the item's team.
    Returns 404 for non-members (not 403, to avoid confirming existence).
    """
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    membership = _get_membership(user, item.team_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Item not found")

    return item


def get_item_with_role(
    db: Session, user: User, item_id: UUID
) -> tuple[WorkItem, Membership]:
    """
    Fetch a work item and the user's membership in its team.
    Returns 404 if item doesn't exist or user isn't a team member.
    """
    item = db.get(WorkItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    membership = _get_membership(user, item.team_id)
    if not membership:
        raise HTTPException(status_code=404, detail="Item not found")

    return item, membership


# ---------------------------------------------------------------------------
# Permission checks
# ---------------------------------------------------------------------------

def can_view(membership: Membership) -> bool:
    """All team members can view."""
    return True


def can_create(membership: Membership) -> bool:
    """Members and above can create items."""
    return _role_level(membership.role) >= _role_level(Role.member)


def can_comment(membership: Membership) -> bool:
    """Members and above can comment."""
    return _role_level(membership.role) >= _role_level(Role.member)


def can_edit(membership: Membership, item: WorkItem, user: User) -> bool:
    """
    Members can edit their own or assigned items.
    Leads and admins can edit any team item.
    """
    if _role_level(membership.role) >= _role_level(Role.lead):
        return True
    if _role_level(membership.role) >= _role_level(Role.member):
        return bool(item.created_by == user.id or item.assignee_id == user.id)
    return False


def can_claim(membership: Membership) -> bool:
    """Members and above can claim unassigned items."""
    return _role_level(membership.role) >= _role_level(Role.member)


def can_assign(membership: Membership) -> bool:
    """Leads and admins can assign/reassign."""
    return _role_level(membership.role) >= _role_level(Role.lead)


def can_release(membership: Membership, item: WorkItem, user: User) -> bool:
    """
    Members can release their own assigned items.
    Leads and admins can release anyone's.
    """
    if _role_level(membership.role) >= _role_level(Role.lead):
        return True
    if _role_level(membership.role) >= _role_level(Role.member):
        return bool(item.assignee_id == user.id)
    return False


def can_change_priority(membership: Membership, item: WorkItem, user: User) -> bool:
    """
    Members can change priority on own/assigned items.
    Leads and admins can change any.
    """
    if _role_level(membership.role) >= _role_level(Role.lead):
        return True
    if _role_level(membership.role) >= _role_level(Role.member):
        return bool(item.created_by == user.id or item.assignee_id == user.id)
    return False


def can_approve(membership: Membership, item: WorkItem, user: User) -> bool:
    """
    Leads and admins can approve, but NOT their own assigned items
    (separation of duties).
    """
    if _role_level(membership.role) < _role_level(Role.lead):
        return False
    # Separation of duties: approver must not be the assignee
    if item.assignee_id == user.id:
        return False
    return True


def can_transition(membership: Membership, item: WorkItem, user: User, to_status: str) -> bool:
    """
    Check if the user can perform a specific transition.
    Delegates to workflow.py for the state machine rules;
    this handles the role-based part.
    """
    from app.workflow import is_valid_transition, get_transition_requirements

    if not is_valid_transition(item.status, to_status):
        return False

    reqs = get_transition_requirements(item.status, to_status)
    if not reqs:
        return False

    # Check role requirement
    min_role = reqs.get("min_role", Role.member)
    if _role_level(membership.role) < _role_level(min_role):
        return False

    # Special rules
    if reqs.get("must_be_assignee") and item.assignee_id != user.id:
        return False
    if reqs.get("must_not_be_assignee") and item.assignee_id == user.id:
        return False

    return True


# ---------------------------------------------------------------------------
# Compute allowed actions for an item (returned to the UI)
# ---------------------------------------------------------------------------

def get_allowed_actions(
    membership: Membership, item: WorkItem, user: User
) -> list[str]:
    """
    Compute the list of actions the user can currently perform on this item.
    This is a UI convenience — every endpoint re-checks independently.
    """
    from app.workflow import TRANSITIONS

    actions = []

    if can_edit(membership, item, user):
        actions.append("edit")

    if can_comment(membership):
        actions.append("comment")

    if item.assignee_id is None and can_claim(membership):
        actions.append("claim")

    if item.assignee_id is not None and can_release(membership, item, user):
        actions.append("release")

    if can_assign(membership):
        actions.append("assign")

    if can_change_priority(membership, item, user):
        actions.append("change_priority")

    # Available transitions
    current_status = item.status.value if hasattr(item.status, "value") else item.status
    for (from_s, to_s) in TRANSITIONS:
        if from_s == current_status:
            if can_transition(membership, item, user, to_s):
                actions.append(f"transition:{to_s}")

    return actions

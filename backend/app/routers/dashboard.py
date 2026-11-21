"""
Dashboard router — aggregated views for the current user.

Sections:
- Assigned to me (open/in_progress, ordered by priority then due date)
- Unassigned urgent (high/critical in my teams)
- Pending my approval (lead/admin, not assignee)
- Overdue (past due_at, not resolved/closed)
- Stale (in_progress with no events for 3 days)

Each section has its own LIMIT query. Nothing loads the whole table.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import (
    ItemEvent,
    ItemPriority,
    ItemStatus,
    Membership,
    Role,
    User,
    WorkItem,
)
from app.policy import get_allowed_actions
from app.schemas import DashboardResponse, DashboardSection, ItemResponse
from app.security import get_current_user

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

SECTION_LIMIT = 10


def _item_to_response(item: WorkItem, membership: Membership, user: User) -> ItemResponse:
    """Convert item to response with allowed_actions."""
    return ItemResponse(
        id=item.id,
        team_id=item.team_id,
        title=item.title,
        description=item.description,
        status=item.status.value if hasattr(item.status, "value") else item.status,
        priority=item.priority.value if hasattr(item.priority, "value") else item.priority,
        assignee_id=item.assignee_id,
        assignee_name=item.assignee.name if item.assignee else None,
        created_by=item.created_by,
        creator_name=item.creator.name if item.creator else None,
        requires_approval=item.requires_approval,
        approved_by=item.approved_by,
        approved_at=item.approved_at,
        due_at=item.due_at,
        version=item.version,
        created_at=item.created_at,
        updated_at=item.updated_at,
        allowed_actions=get_allowed_actions(membership, item, user),
    )


def _get_membership_for_team(user: User, team_id) -> Membership | None:
    for m in user.memberships:
        if m.team_id == team_id:
            return m
    return None


@router.get("", response_model=DashboardResponse)
def get_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the dashboard for the current user."""
    user_team_ids = [m.team_id for m in user.memberships]
    if not user_team_ids:
        return DashboardResponse(sections=[], status_counts={})

    sections = []

    # 1. Assigned to me (not closed)
    assigned_items = (
        db.query(WorkItem)
        .filter(
            WorkItem.assignee_id == user.id,
            WorkItem.status.notin_([ItemStatus.resolved, ItemStatus.closed]),
        )
        .order_by(WorkItem.priority.desc(), WorkItem.due_at.asc().nullslast(), WorkItem.updated_at.desc())
        .limit(SECTION_LIMIT)
        .all()
    )
    sections.append(DashboardSection(
        label="Assigned to me",
        items=[
            _item_to_response(i, _get_membership_for_team(user, i.team_id), user)
            for i in assigned_items
            if _get_membership_for_team(user, i.team_id)
        ],
        count=len(assigned_items),
    ))

    # 2. Unassigned urgent (high/critical in my teams)
    urgent_items = (
        db.query(WorkItem)
        .filter(
            WorkItem.team_id.in_(user_team_ids),
            WorkItem.assignee_id.is_(None),
            WorkItem.priority.in_([ItemPriority.high, ItemPriority.critical]),
            WorkItem.status.notin_([ItemStatus.resolved, ItemStatus.closed]),
        )
        .order_by(WorkItem.priority.desc(), WorkItem.created_at.asc())
        .limit(SECTION_LIMIT)
        .all()
    )
    sections.append(DashboardSection(
        label="Unassigned urgent",
        items=[
            _item_to_response(i, _get_membership_for_team(user, i.team_id), user)
            for i in urgent_items
            if _get_membership_for_team(user, i.team_id)
        ],
        count=len(urgent_items),
    ))

    # 3. Pending my approval (lead/admin, not assignee)
    lead_team_ids = [
        m.team_id for m in user.memberships
        if m.role in (Role.lead, Role.admin)
    ]
    if lead_team_ids:
        pending_items = (
            db.query(WorkItem)
            .filter(
                WorkItem.team_id.in_(lead_team_ids),
                WorkItem.status == ItemStatus.pending_approval,
                WorkItem.assignee_id != user.id,  # separation of duties
            )
            .order_by(WorkItem.updated_at.asc())
            .limit(SECTION_LIMIT)
            .all()
        )
        sections.append(DashboardSection(
            label="Pending my approval",
            items=[
                _item_to_response(i, _get_membership_for_team(user, i.team_id), user)
                for i in pending_items
                if _get_membership_for_team(user, i.team_id)
            ],
            count=len(pending_items),
        ))

    # 4. Overdue (past due_at, not resolved/closed)
    now = datetime.now(timezone.utc)
    overdue_items = (
        db.query(WorkItem)
        .filter(
            WorkItem.team_id.in_(user_team_ids),
            WorkItem.due_at < now,
            WorkItem.status.notin_([ItemStatus.resolved, ItemStatus.closed]),
        )
        .order_by(WorkItem.due_at.asc())
        .limit(SECTION_LIMIT)
        .all()
    )
    sections.append(DashboardSection(
        label="Overdue",
        items=[
            _item_to_response(i, _get_membership_for_team(user, i.team_id), user)
            for i in overdue_items
            if _get_membership_for_team(user, i.team_id)
        ],
        count=len(overdue_items),
    ))

    # 5. Stale: in_progress with no events for 3 days
    stale_cutoff = now - timedelta(days=3)
    # Subquery: latest event per item
    latest_event = (
        db.query(
            ItemEvent.item_id,
            func.max(ItemEvent.created_at).label("last_event_at"),
        )
        .group_by(ItemEvent.item_id)
        .subquery()
    )

    stale_items = (
        db.query(WorkItem)
        .outerjoin(latest_event, WorkItem.id == latest_event.c.item_id)
        .filter(
            WorkItem.team_id.in_(user_team_ids),
            WorkItem.status == ItemStatus.in_progress,
            or_(
                latest_event.c.last_event_at < stale_cutoff,
                latest_event.c.last_event_at.is_(None),
            ),
        )
        .order_by(WorkItem.updated_at.asc())
        .limit(SECTION_LIMIT)
        .all()
    )
    sections.append(DashboardSection(
        label="Stale (no activity for 3+ days)",
        items=[
            _item_to_response(i, _get_membership_for_team(user, i.team_id), user)
            for i in stale_items
            if _get_membership_for_team(user, i.team_id)
        ],
        count=len(stale_items),
    ))

    # Status counts across all user's teams
    status_counts_query = (
        db.query(WorkItem.status, func.count(WorkItem.id))
        .filter(WorkItem.team_id.in_(user_team_ids))
        .group_by(WorkItem.status)
        .all()
    )
    status_counts = {
        (s.value if hasattr(s, "value") else s): c
        for s, c in status_counts_query
    }

    return DashboardResponse(sections=sections, status_counts=status_counts)

"""
Item service — business logic and atomic updates.

All item mutations go through this module. It handles:
- Atomic claim (conditional UPDATE, not read-then-write)
- Optimistic locking (version check on every mutation)
- Event creation in the same transaction
- Outbox row creation in the same transaction
"""

import base64
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, text, update
from sqlalchemy.orm import Session

from app.models import (
    Comment,
    ItemEvent,
    ItemPriority,
    ItemStatus,
    Membership,
    Outbox,
    OutboxStatus,
    Role,
    User,
    WorkItem,
)
from app.schemas import (
    AssignRequest,
    CommentCreateRequest,
    CommentResponse,
    EventListResponse,
    EventResponse,
    ItemCreateRequest,
    ItemListResponse,
    ItemResponse,
    ItemUpdateRequest,
    TransitionRequest,
)
from app.policy import (
    can_assign,
    can_change_priority,
    can_claim,
    can_comment,
    can_create,
    can_edit,
    can_release,
    get_allowed_actions,
    get_item_for_user,
    get_item_with_role,
)
from app.workflow import check_transition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _item_to_response(item: WorkItem, membership: Membership, user: User) -> ItemResponse:
    """Convert a WorkItem model to an ItemResponse with allowed_actions."""
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


def _add_event(
    db: Session, item_id: UUID, actor_id: UUID, event_type: str, payload: dict | None = None
) -> ItemEvent:
    """Create an event in the same transaction."""
    event = ItemEvent(
        item_id=item_id,
        actor_id=actor_id,
        type=event_type,
        payload=payload,
    )
    db.add(event)
    db.flush()
    return event


def _add_outbox(db: Session, event_type: str, payload: dict) -> Outbox:
    """Create an outbox row in the same transaction."""
    outbox = Outbox(
        type=event_type,
        payload=payload,
        status=OutboxStatus.pending,
    )
    db.add(outbox)
    db.flush()
    return outbox


def _require_version(version: int | None) -> int:
    """Require a version number for mutations. Returns 428 if missing."""
    if version is None:
        raise HTTPException(
            status_code=428,
            detail="Version header (If-Match) is required for this operation",
        )
    return version


def _encode_cursor(updated_at: datetime, item_id: UUID) -> str:
    """Encode a keyset pagination cursor."""
    data = {"u": updated_at.isoformat(), "i": str(item_id)}
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    """Decode a keyset pagination cursor. Returns 422 on invalid."""
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor))
        return datetime.fromisoformat(data["u"]), UUID(data["i"])
    except Exception:
        raise HTTPException(status_code=422, detail="Invalid cursor")


# ---------------------------------------------------------------------------
# CRUD Operations
# ---------------------------------------------------------------------------

def create_item(
    db: Session, user: User, body: ItemCreateRequest
) -> ItemResponse:
    """Create a new work item."""
    # Check team membership
    membership = None
    for m in user.memberships:
        if m.team_id == body.team_id:
            membership = m
            break

    if not membership:
        raise HTTPException(status_code=404, detail="Team not found")

    if not can_create(membership):
        raise HTTPException(status_code=403, detail="Viewers cannot create items")

    item = WorkItem(
        team_id=body.team_id,
        title=body.title,
        description=body.description,
        priority=ItemPriority(body.priority),
        requires_approval=body.requires_approval,
        due_at=body.due_at,
        created_by=user.id,
        status=ItemStatus.open,
    )
    db.add(item)
    db.flush()

    # Update search vector
    if db.bind and db.bind.dialect.name != "sqlite":
        db.execute(
            text(
                "UPDATE work_items SET search_vector = "
                "to_tsvector('english', coalesce(:title, '') || ' ' || coalesce(:desc, '')) "
                "WHERE id = :id"
            ),
            {"title": item.title, "desc": item.description or "", "id": item.id},
        )

    # Event
    _add_event(db, item.id, user.id, "item.created", {
        "title": item.title,
        "priority": body.priority,
    })

    # Outbox
    _add_outbox(db, "item.created", {
        "item_id": str(item.id),
        "team_id": str(body.team_id),
        "created_by": str(user.id),
        "title": item.title,
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


def get_item(db: Session, user: User, item_id: UUID) -> ItemResponse:
    """Get a single work item by ID."""
    item, membership = get_item_with_role(db, user, item_id)
    return _item_to_response(item, membership, user)


# Whitelist of sortable columns
SORT_COLUMNS = {
    "updated_at": WorkItem.updated_at,
    "created_at": WorkItem.created_at,
    "priority": WorkItem.priority,
    "status": WorkItem.status,
    "title": WorkItem.title,
}


def list_items(
    db: Session,
    user: User,
    team_id: UUID | None = None,
    status: str | None = None,
    priority: str | None = None,
    assignee_id: UUID | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = 20,
) -> ItemListResponse:
    """
    List work items with keyset pagination, filtering, and search.
    Only returns items from teams the user belongs to.
    """
    limit = min(limit, 100)  # Cap at 100

    # Get user's team IDs
    user_team_ids = [m.team_id for m in user.memberships]
    if not user_team_ids:
        return ItemListResponse(items=[], next_cursor=None)

    # Base query
    query = db.query(WorkItem).filter(WorkItem.team_id.in_(user_team_ids))

    # Filters
    if team_id:
        if team_id not in user_team_ids:
            raise HTTPException(status_code=404, detail="Team not found")
        query = query.filter(WorkItem.team_id == team_id)

    if status:
        query = query.filter(WorkItem.status == ItemStatus(status))

    if priority:
        query = query.filter(WorkItem.priority == ItemPriority(priority))

    if assignee_id:
        query = query.filter(WorkItem.assignee_id == assignee_id)

    # Full-text search
    if q:
        if db.bind and db.bind.dialect.name == "sqlite":
            query = query.filter(
                or_(WorkItem.title.ilike(f"%{q}%"), WorkItem.description.ilike(f"%{q}%"))
            )
        else:
            query = query.filter(
                WorkItem.search_vector.op("@@")(func.plainto_tsquery("english", q))
            )

    # Keyset pagination
    if cursor:
        cursor_updated_at, cursor_id = _decode_cursor(cursor)
        query = query.filter(
            or_(
                WorkItem.updated_at < cursor_updated_at,
                and_(
                    WorkItem.updated_at == cursor_updated_at,
                    WorkItem.id < cursor_id,
                ),
            )
        )

    # Order: newest updates first, then by ID for deterministic order
    query = query.order_by(WorkItem.updated_at.desc(), WorkItem.id.desc())

    # Fetch one extra to determine if there's a next page
    items = query.limit(limit + 1).all()

    has_next = len(items) > limit
    items = items[:limit]

    next_cursor = None
    if has_next and items:
        last = items[-1]
        next_cursor = _encode_cursor(last.updated_at, last.id)

    # Build responses
    result_items = []
    for item in items:
        membership = None
        for m in user.memberships:
            if m.team_id == item.team_id:
                membership = m
                break
        if membership:
            result_items.append(_item_to_response(item, membership, user))

    return ItemListResponse(items=result_items, next_cursor=next_cursor)


def update_item(
    db: Session, user: User, item_id: UUID, body: ItemUpdateRequest, version: int | None
) -> ItemResponse:
    """
    Update item fields with optimistic locking.
    Version mismatch returns 409 with current item state.
    """
    v = _require_version(version)

    item, membership = get_item_with_role(db, user, item_id)

    if not can_edit(membership, item, user):
        raise HTTPException(status_code=403, detail="You cannot edit this item")

    # Check priority change permission separately
    if body.priority is not None and not can_change_priority(membership, item, user):
        raise HTTPException(status_code=403, detail="You cannot change priority on this item")

    # Optimistic locking: version must match
    changes = {}
    if body.title is not None:
        changes["title"] = body.title
    if body.description is not None:
        changes["description"] = body.description
    if body.priority is not None:
        changes["priority"] = ItemPriority(body.priority)
    if body.requires_approval is not None:
        changes["requires_approval"] = body.requires_approval
    if body.due_at is not None:
        changes["due_at"] = body.due_at

    if not changes:
        return _item_to_response(item, membership, user)

    # Atomic update with version check
    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == item_id, WorkItem.version == v)
        .values(
            **changes,
            version=WorkItem.version + 1,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(WorkItem.version)
    )

    row = result.fetchone()
    if row is None:
        db.refresh(item)
        raise HTTPException(
            status_code=409,
            detail="Item was modified by someone else",
            headers={"X-Current-Version": str(item.version)},
        )

    # Update search vector if title or description changed
    if "title" in changes or "description" in changes:
        new_title = changes.get("title", item.title)
        new_desc = changes.get("description", item.description) or ""
        if db.bind and db.bind.dialect.name != "sqlite":
            db.execute(
                text(
                    "UPDATE work_items SET search_vector = "
                    "to_tsvector('english', coalesce(:title, '') || ' ' || coalesce(:desc, '')) "
                    "WHERE id = :id"
                ),
                {"title": new_title, "desc": new_desc, "id": item_id},
            )

    # Event
    _add_event(db, item_id, user.id, "item.updated", payload={
        k: str(v) if not isinstance(v, str) else v for k, v in changes.items()
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


# ---------------------------------------------------------------------------
# Claim, Assign, Release
# ---------------------------------------------------------------------------

def claim_item(db: Session, user: User, item_id: UUID) -> ItemResponse:
    """
    Atomic claim: single UPDATE with WHERE assignee_id IS NULL.
    No read-then-write. Loser gets 409 with current assignee.
    """
    item, membership = get_item_with_role(db, user, item_id)

    if not can_claim(membership):
        raise HTTPException(status_code=403, detail="You cannot claim items")

    # Atomic conditional update
    now = datetime.now(timezone.utc)
    claim_stmt = (
        update(WorkItem)
        .where(WorkItem.id == item_id, WorkItem.assignee_id.is_(None))
        .values(
            assignee_id=user.id,
            status=case(
                (WorkItem.status == ItemStatus.open, ItemStatus.in_progress),
                else_=WorkItem.status,
            ),
            version=WorkItem.version + 1,
            updated_at=now,
        )
        .returning(WorkItem.version)
    )
    result = db.execute(claim_stmt)
    row = result.fetchone()
    if row is None:
        db.refresh(item)
        assignee_name = item.assignee.name if item.assignee else "someone"
        raise HTTPException(
            status_code=409,
            detail=f"Item already claimed by {assignee_name}",
        )

    # Event and outbox in the same transaction
    _add_event(db, item_id, user.id, "item.claimed", {
        "assignee_id": str(user.id),
        "assignee_name": user.name,
    })

    _add_outbox(db, "item.assigned", {
        "item_id": str(item_id),
        "assignee_id": str(user.id),
        "assigned_by": str(user.id),
        "team_id": str(item.team_id),
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


def assign_item(
    db: Session, user: User, item_id: UUID, body: AssignRequest, version: int | None
) -> ItemResponse:
    """Assign an item to a specific user (lead+ only)."""
    v = _require_version(version)

    item, membership = get_item_with_role(db, user, item_id)

    if not can_assign(membership):
        raise HTTPException(status_code=403, detail="Only leads and admins can assign items")

    # Verify target user is a member of the item's team
    target_user = db.get(User, body.assignee_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")

    target_membership = None
    for m in target_user.memberships:
        if m.team_id == item.team_id:
            target_membership = m
            break
    if not target_membership:
        raise HTTPException(
            status_code=422,
            detail="Target user is not a member of the item's team",
        )

    # Atomic update with version check
    new_status = "in_progress" if item.status == ItemStatus.open else item.status
    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == item_id, WorkItem.version == v)
        .values(
            assignee_id=body.assignee_id,
            status=new_status,
            version=WorkItem.version + 1,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(WorkItem.version)
    )

    row = result.fetchone()
    if row is None:
        db.refresh(item)
        raise HTTPException(status_code=409, detail="Item was modified by someone else")

    # Event
    _add_event(db, item_id, user.id, "item.assigned", {
        "assignee_id": str(body.assignee_id),
        "assignee_name": target_user.name,
        "assigned_by": user.name,
    })

    # Outbox
    _add_outbox(db, "item.assigned", {
        "item_id": str(item_id),
        "assignee_id": str(body.assignee_id),
        "assigned_by": str(user.id),
        "team_id": str(item.team_id),
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


def release_item(
    db: Session, user: User, item_id: UUID, version: int | None
) -> ItemResponse:
    """Release (unassign) an item."""
    v = _require_version(version)

    item, membership = get_item_with_role(db, user, item_id)

    if not can_release(membership, item, user):
        raise HTTPException(status_code=403, detail="You cannot release this item")

    if item.assignee_id is None:
        raise HTTPException(status_code=409, detail="Item is not assigned to anyone")

    old_assignee_id = item.assignee_id

    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == item_id, WorkItem.version == v)
        .values(
            assignee_id=None,
            status=ItemStatus.open,
            version=WorkItem.version + 1,
            updated_at=datetime.now(timezone.utc),
        )
        .returning(WorkItem.version)
    )

    row = result.fetchone()
    if row is None:
        db.refresh(item)
        raise HTTPException(status_code=409, detail="Item was modified by someone else")

    _add_event(db, item_id, user.id, "item.released", {
        "previous_assignee_id": str(old_assignee_id),
        "released_by": user.name,
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

def transition_item(
    db: Session, user: User, item_id: UUID, body: TransitionRequest, version: int | None
) -> ItemResponse:
    """
    Transition an item's status according to the workflow state machine.
    Validates all rules including separation of duties.
    """
    v = _require_version(version)

    item, membership = get_item_with_role(db, user, item_id)

    # 1. Viewers cannot transition any item (RBAC 403)
    from app.policy import _role_level
    if _role_level(membership.role) < _role_level(Role.member):
        raise HTTPException(status_code=403, detail="Viewers cannot transition items")

    # 2. Check transition validity according to state machine rules (409 Conflict)
    allowed, reason = check_transition(item, user, body.to, body.comment)
    if not allowed:
        raise HTTPException(status_code=409, detail=reason)

    # 3. Check minimum role for this specific valid transition (RBAC 403)
    from app.workflow import get_transition_requirements
    from_status = item.status.value if hasattr(item.status, "value") else item.status
    reqs = get_transition_requirements(from_status, body.to)
    if reqs:
        min_role = reqs.get("min_role", Role.member)
        if _role_level(membership.role) < _role_level(min_role):
            raise HTTPException(status_code=403, detail="You do not have permission for this transition")

    # Build update values
    values: dict = {
        "status": ItemStatus(body.to),
        "version": WorkItem.version + 1,
        "updated_at": datetime.now(timezone.utc),
    }

    # Handle approval
    if body.to == "resolved" and item.status == ItemStatus.pending_approval:
        values["approved_by"] = user.id
        values["approved_at"] = datetime.now(timezone.utc)

    # Handle reopen: clear approval fields
    if body.to == "open" and item.status == ItemStatus.resolved:
        values["approved_by"] = None
        values["approved_at"] = None

    # Atomic update with version check
    result = db.execute(
        update(WorkItem)
        .where(WorkItem.id == item_id, WorkItem.version == v)
        .values(**values)
        .returning(WorkItem.version)
    )

    row = result.fetchone()
    if row is None:
        db.refresh(item)
        raise HTTPException(status_code=409, detail="Item was modified by someone else")

    from_status = item.status.value if hasattr(item.status, "value") else item.status

    # Event
    event_payload = {
        "from": from_status,
        "to": body.to,
    }
    if body.comment:
        event_payload["comment"] = body.comment

    _add_event(db, item_id, user.id, "item.transitioned", event_payload)

    # Add comment for rejection
    if body.comment:
        comment = Comment(
            item_id=item_id,
            author_id=user.id,
            body=body.comment,
        )
        db.add(comment)
        db.flush()

    # Outbox
    _add_outbox(db, f"item.{body.to}", {
        "item_id": str(item_id),
        "from_status": from_status,
        "to_status": body.to,
        "actor_id": str(user.id),
        "team_id": str(item.team_id),
        "assignee_id": str(item.assignee_id) if item.assignee_id else None,
    })

    db.refresh(item)
    return _item_to_response(item, membership, user)


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

def create_comment(
    db: Session, user: User, item_id: UUID, body: CommentCreateRequest
) -> CommentResponse:
    """Add a comment to a work item."""
    item, membership = get_item_with_role(db, user, item_id)

    if not can_comment(membership):
        raise HTTPException(status_code=403, detail="Viewers cannot comment")

    comment = Comment(
        item_id=item_id,
        author_id=user.id,
        body=body.body,
    )
    db.add(comment)
    db.flush()

    _add_event(db, item_id, user.id, "comment.added", {
        "comment_id": str(comment.id),
        "body_preview": body.body[:100],
    })

    _add_outbox(db, "comment.added", {
        "item_id": str(item_id),
        "comment_id": str(comment.id),
        "author_id": str(user.id),
        "team_id": str(item.team_id),
        "assignee_id": str(item.assignee_id) if item.assignee_id else None,
        "created_by": str(item.created_by),
    })

    return CommentResponse(
        id=comment.id,
        item_id=comment.item_id,
        author_id=comment.author_id,
        author_name=user.name,
        body=comment.body,
        created_at=comment.created_at,
    )


def list_comments(db: Session, user: User, item_id: UUID) -> list[CommentResponse]:
    """List comments for a work item."""
    get_item_for_user(db, user, item_id)

    comments = (
        db.query(Comment)
        .filter(Comment.item_id == item_id)
        .order_by(Comment.created_at.asc())
        .all()
    )

    return [
        CommentResponse(
            id=c.id,
            item_id=c.item_id,
            author_id=c.author_id,
            author_name=c.author.name if c.author else None,
            body=c.body,
            created_at=c.created_at,
        )
        for c in comments
    ]


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

def list_events(
    db: Session, user: User, item_id: UUID, cursor: str | None = None, limit: int = 50
) -> EventListResponse:
    """List events for a work item with keyset pagination."""
    limit = min(limit, 100)
    get_item_for_user(db, user, item_id)

    query = db.query(ItemEvent).filter(ItemEvent.item_id == item_id)

    if cursor:
        try:
            cursor_id = int(base64.urlsafe_b64decode(cursor))
        except Exception:
            raise HTTPException(status_code=422, detail="Invalid cursor")
        query = query.filter(ItemEvent.id < cursor_id)

    query = query.order_by(ItemEvent.id.desc())
    events = query.limit(limit + 1).all()

    has_next = len(events) > limit
    events = events[:limit]

    next_cursor = None
    if has_next and events:
        next_cursor = base64.urlsafe_b64encode(str(events[-1].id).encode()).decode()

    return EventListResponse(
        events=[
            EventResponse(
                id=e.id,
                item_id=e.item_id,
                actor_id=e.actor_id,
                actor_name=e.actor.name if e.actor else None,
                type=e.type,
                payload=e.payload,
                created_at=e.created_at,
            )
            for e in events
        ],
        next_cursor=next_cursor,
    )

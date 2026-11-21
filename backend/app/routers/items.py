"""
Items router — CRUD, claim, assign, release, transitions, comments, events.

All routes require authentication. Authorization is delegated to policy.py
and item_service.py. Version header (If-Match) required for mutations.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.db import get_db
from app.idempotency import check_idempotency, compute_request_hash, store_idempotency_response
from app.models import User
from app.schemas import (
    AssignRequest,
    CommentCreateRequest,
    CommentResponse,
    EventListResponse,
    ItemCreateRequest,
    ItemListResponse,
    ItemResponse,
    ItemUpdateRequest,
    TransitionRequest,
)
from app.security import get_current_user
from app.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


@router.post("", response_model=ItemResponse, status_code=201)
async def create_item(
    request: Request,
    body: ItemCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    """Create a new work item. Idempotency-Key header required."""
    if not idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")

    # Check idempotency
    raw_body = await request.body()
    req_hash = compute_request_hash("/items", raw_body)
    replay = check_idempotency(db, user.id, idempotency_key, "/items", req_hash)
    if replay:
        return ItemResponse(**replay["body"])

    # Create the item
    result = item_service.create_item(db, user, body)

    # Store idempotency response
    store_idempotency_response(
        db, user.id, idempotency_key, "/items", req_hash,
        201, result.model_dump(mode="json"),
    )

    return result


@router.get("", response_model=ItemListResponse)
def list_items(
    team_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    assignee: UUID | None = Query(default=None, alias="assignee_id"),
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List work items with filtering, search, and keyset pagination.
    Only items from the user's teams are returned.
    """
    return item_service.list_items(
        db, user,
        team_id=team_id,
        status=status,
        priority=priority,
        assignee_id=assignee,
        q=q,
        cursor=cursor,
        limit=limit,
    )


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a single work item. Returns 404 if not found or not in user's team."""
    return item_service.get_item(db, user, item_id)


@router.patch("/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: UUID,
    body: ItemUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    if_match: int | None = Header(default=None, alias="If-Match"),
):
    """Update item fields. Requires If-Match version header."""
    return item_service.update_item(db, user, item_id, body, if_match)


@router.post("/{item_id}/claim", response_model=ItemResponse)
def claim_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Claim an unassigned item. Atomic — if two people click at the same time,
    exactly one wins and the other gets 409 with the winner's name.
    """
    return item_service.claim_item(db, user, item_id)


@router.post("/{item_id}/assign", response_model=ItemResponse)
def assign_item(
    item_id: UUID,
    body: AssignRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    if_match: int | None = Header(default=None, alias="If-Match"),
):
    """Assign an item to a specific user. Lead+ only."""
    return item_service.assign_item(db, user, item_id, body, if_match)


@router.post("/{item_id}/release", response_model=ItemResponse)
def release_item(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    if_match: int | None = Header(default=None, alias="If-Match"),
):
    """Release (unassign) an item."""
    return item_service.release_item(db, user, item_id, if_match)


@router.post("/{item_id}/transition", response_model=ItemResponse)
def transition_item(
    item_id: UUID,
    body: TransitionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    if_match: int | None = Header(default=None, alias="If-Match"),
):
    """Transition an item's status according to the workflow state machine."""
    return item_service.transition_item(db, user, item_id, body, if_match)


@router.post("/{item_id}/comments", response_model=CommentResponse, status_code=201)
def create_comment(
    item_id: UUID,
    body: CommentCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a comment to a work item."""
    return item_service.create_comment(db, user, item_id, body)


@router.get("/{item_id}/comments", response_model=list[CommentResponse])
def list_comments(
    item_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List comments for a work item."""
    return item_service.list_comments(db, user, item_id)


@router.get("/{item_id}/events", response_model=EventListResponse)
def list_events(
    item_id: UUID,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List the event history for a work item."""
    return item_service.list_events(db, user, item_id, cursor, limit)

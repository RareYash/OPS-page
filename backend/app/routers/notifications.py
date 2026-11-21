"""
Notifications router — list and mark as read.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.db import get_db
from app.models import Notification, User
from app.schemas import NotificationListResponse, NotificationResponse
from app.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    limit: int = Query(default=20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List notifications for the current user, newest first."""
    notifications = (
        db.query(Notification)
        .filter(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )

    unread_count = db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
    ).scalar()

    return NotificationListResponse(
        notifications=[
            NotificationResponse.model_validate(n) for n in notifications
        ],
        unread_count=unread_count or 0,
    )


@router.post("/{notification_id}/read")
def mark_read(
    notification_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Mark a notification as read."""
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")

    notification.read_at = datetime.now(timezone.utc)
    db.flush()

    return {"message": "Marked as read"}

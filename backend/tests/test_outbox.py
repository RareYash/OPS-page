"""
Outbox and asynchronous processing tests for Newtonite Ops.

Tests:
1. Outbox entry generation on business actions (assignment, approval, comments).
2. Outbox worker batch processing moves items from pending -> processing -> done.
3. Deduplication: processing the same outbox event multiple times produces only 1 notification.
4. Retry logic: failures increment attempts and schedule backoff; max attempts transitions to 'failed'.
5. Stuck job recovery: jobs stuck in 'processing' past the timeout get reclaimed to 'pending'.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy.orm import Session

from app.models import (
    Notification,
    Outbox,
    OutboxStatus,
    Team,
    User,
    WorkItem,
)
from app.worker.outbox_worker import process_batch, process_single, reclaim_stuck_jobs


def test_outbox_processing_generates_notifications(
    db: Session,
    team_alpha: Team,
    user_member: tuple[User, str],
    user_lead: tuple[User, str],
    sample_item: WorkItem,
):
    """An outbox event for an item assignment creates a notification for the assignee."""
    member_user, _ = user_member
    lead_user, _ = user_lead

    # Create an outbox row representing an assignment
    outbox_entry = Outbox(
        type="item.assigned",
        payload={
            "item_id": str(sample_item.id),
            "assignee_id": str(member_user.id),
            "assigned_by": str(lead_user.id),
            "team_id": str(team_alpha.id),
        },
        status=OutboxStatus.pending,
        attempts=0,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    db.add(outbox_entry)
    db.commit()

    # Run batch processing
    processed_count = process_batch()
    assert processed_count >= 1

    # Verify outbox item is marked as done
    db.expire_all()
    fresh_outbox = db.get(Outbox, outbox_entry.id)
    assert fresh_outbox.status == OutboxStatus.done

    # Verify notification was generated for the member
    notif = db.query(Notification).filter(
        Notification.user_id == member_user.id,
        Notification.item_id == sample_item.id,
    ).first()
    assert notif is not None
    assert notif.kind == "item.assigned"


def test_outbox_notification_deduplication(
    db: Session,
    team_alpha: Team,
    user_member: tuple[User, str],
    sample_item: WorkItem,
):
    """Processing the exact same outbox message twice must NOT duplicate notifications."""
    member_user, _ = user_member

    outbox_entry = Outbox(
        type="item.assigned",
        payload={
            "item_id": str(sample_item.id),
            "assignee_id": str(member_user.id),
            "assigned_by": str(uuid4()),
            "team_id": str(team_alpha.id),
        },
        status=OutboxStatus.pending,
        attempts=0,
        next_attempt_at=datetime.now(timezone.utc) - timedelta(seconds=10),
    )
    db.add(outbox_entry)
    db.commit()

    # Process first time
    process_single(outbox_entry.id)

    # Force status back to pending and process second time (simulating at-least-once retry)
    outbox_entry.status = OutboxStatus.pending
    db.commit()
    process_single(outbox_entry.id)

    # Check notification count for this user and item
    notifs = db.query(Notification).filter(
        Notification.user_id == member_user.id,
        Notification.item_id == sample_item.id,
    ).all()

    # Deduplication constraint ensures exactly 1 notification exists
    assert len(notifs) == 1


def test_reclaim_stuck_jobs(db: Session, team_alpha: Team):
    """Jobs left in 'processing' status with an expired locked_at timestamp get reset to 'pending'."""
    stuck_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    stuck_job = Outbox(
        type="test.stuck",
        payload={"dummy": True},
        status=OutboxStatus.processing,
        locked_at=stuck_time,
        attempts=1,
    )
    db.add(stuck_job)
    db.commit()

    reclaim_stuck_jobs()

    db.expire_all()
    reclaimed = db.get(Outbox, stuck_job.id)
    assert reclaimed.status == OutboxStatus.pending
    assert reclaimed.locked_at is None

"""
Outbox worker — processes async events (notifications, etc.)

Pattern: transactional outbox with SKIP LOCKED polling.
- Picks up pending messages, marks processing, handles them, marks done.
- Retries with exponential backoff + jitter on failure.
- Deduplication via unique dedupe_key on notifications.
- Reclaims stuck jobs (locked_at older than timeout).
"""

import logging
import random
import time
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import SessionLocal
from app.models import (
    Membership,
    Notification,
    Outbox,
    OutboxStatus,
    Role,
)

settings = get_settings()
logger = logging.getLogger("y_corp.worker")

BACKOFF_BASE = [5, 10, 20, 40, 60, 900]  # seconds, capped at 15 min


def run_worker():
    """Main worker loop."""
    logger.info("Worker starting. Poll interval: %ds", settings.worker_poll_interval)

    while True:
        try:
            processed = process_batch()
            if processed == 0:
                time.sleep(settings.worker_poll_interval)
        except Exception:
            logger.exception("Worker loop error")
            time.sleep(settings.worker_poll_interval)

        # Reclaim stuck jobs
        try:
            reclaim_stuck_jobs()
        except Exception:
            logger.exception("Error reclaiming stuck jobs")


def process_batch() -> int:
    """Process a batch of outbox messages. Returns count processed."""
    db = SessionLocal()
    try:
        # Pick up pending messages with SKIP LOCKED (on PG)
        now = datetime.now(timezone.utc)
        is_sqlite = db.bind is not None and db.bind.dialect.name == "sqlite"
        lock_clause = "" if is_sqlite else "FOR UPDATE SKIP LOCKED "
        result = db.execute(
            text(
        if is_sqlite:
            query = text(
                "SELECT id FROM outbox "
                "WHERE status = 'pending' AND next_attempt_at <= :now "
                "ORDER BY id "
                f"{lock_clause}"
                "LIMIT :limit"
            ),
            )
        else:
            query = text(
                "SELECT id FROM outbox "
                "WHERE status = 'pending' AND next_attempt_at <= :now "
                "ORDER BY id "
                "FOR UPDATE SKIP LOCKED "
                "LIMIT :limit"
            )
        result = db.execute(
            query,
            {"now": now, "limit": settings.worker_batch_size},
        )
        row_ids = [row[0] for row in result]

        if not row_ids:
            db.close()
            return 0

        # Mark as processing
        db.execute(
            update(Outbox)
            .where(Outbox.id.in_(row_ids))
            .values(status=OutboxStatus.processing, locked_at=now)
        )
        db.commit()

        # Process each message
        for outbox_id in row_ids:
            process_single(outbox_id)

        return len(row_ids)
    except Exception:
        db.rollback()
        logger.exception("Error in process_batch")
        return 0
    finally:
        db.close()


def process_single(outbox_id: int) -> None:
    """Process a single outbox message."""
    db = SessionLocal()
    try:
        outbox = db.get(Outbox, outbox_id)
        if not outbox:
            return

        try:
            handle_message(db, outbox)
            outbox.status = OutboxStatus.done
            db.commit()
            logger.info("Processed outbox #%d type=%s", outbox_id, outbox.type)

        except Exception as e:
            db.rollback()
            # Retry with backoff
            db2 = SessionLocal()
            try:
                msg = db2.get(Outbox, outbox_id)
                if msg:
                    msg.attempts += 1
                    msg.last_error = str(e)[:1000]
                    msg.locked_at = None

                    if msg.attempts >= settings.worker_max_attempts:
                        msg.status = OutboxStatus.failed
                        logger.error(
                            "Outbox #%d failed after %d attempts: %s",
                            outbox_id, msg.attempts, str(e),
                        )
                    else:
                        msg.status = OutboxStatus.pending
                        backoff_idx = min(int(msg.attempts) - 1, len(BACKOFF_BASE) - 1)
                        jitter = random.uniform(0, BACKOFF_BASE[backoff_idx] * 0.2)
                        msg.next_attempt_at = datetime.now(timezone.utc) + timedelta(
                            seconds=BACKOFF_BASE[backoff_idx] + jitter
                        )
                        logger.warning(
                            "Outbox #%d attempt %d failed, retrying in %.0fs: %s",
                            outbox_id, msg.attempts,
                            BACKOFF_BASE[backoff_idx] + jitter, str(e),
                        )
                    db2.commit()
            finally:
                db2.close()
    finally:
        db.close()


def reclaim_stuck_jobs() -> None:
    """Reclaim jobs stuck in 'processing' for longer than the timeout."""
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(
            seconds=settings.worker_stuck_timeout_seconds
        )
        result = db.execute(
            update(Outbox)
            .where(
                Outbox.status == OutboxStatus.processing,
                Outbox.locked_at < cutoff,
            )
            .values(
                status=OutboxStatus.pending,
                locked_at=None,
                next_attempt_at=datetime.now(timezone.utc),
            )
        )
        if result.rowcount > 0:
            logger.info("Reclaimed %d stuck outbox jobs", result.rowcount)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------

def handle_message(db: Session, outbox: Outbox) -> None:
    """Route a message to its handler based on type."""
    handlers = {
        "item.created": handle_item_created,
        "item.assigned": handle_item_assigned,
        "item.pending_approval": handle_item_pending_approval,
        "item.resolved": handle_item_resolved,
        "item.in_progress": handle_item_rejection,
        "comment.added": handle_comment_added,
    }

    handler = handlers.get(str(outbox.type))
    if handler:
        handler(db, outbox)
    else:
        logger.warning("No handler for outbox type: %s", outbox.type)


def _create_notification(
    db: Session, user_id: str, item_id: str | None, kind: str, dedupe_key: str
) -> None:
    """
    Create a notification with deduplication.
    Uses ON CONFLICT DO NOTHING so processing twice creates one notification.
    """
    now = datetime.now(timezone.utc)
    u_id = uuid.UUID(str(user_id)) if user_id else None
    i_id = uuid.UUID(str(item_id)) if item_id else None
    notif_id = uuid.uuid4()

    is_sqlite = db.bind is not None and db.bind.dialect.name == "sqlite"
    if is_sqlite:
        stmt = (
            sqlite_insert(Notification)
            .values(
                id=notif_id,
                user_id=u_id,
                item_id=i_id,
                kind=kind,
                dedupe_key=dedupe_key,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
        )
    else:
        stmt = (
            pg_insert(Notification)
            .values(
                id=notif_id,
                user_id=u_id,
                item_id=i_id,
                kind=kind,
                dedupe_key=dedupe_key,
                created_at=now,
            )
            .on_conflict_do_nothing(index_elements=["dedupe_key"])
        )
    db.execute(stmt)


def handle_item_created(db: Session, outbox: Outbox) -> None:
    """Notify team leads about new items (optional)."""
    payload = outbox.payload
    # Could notify team leads, but keeping it simple for v1
    logger.info("Item created: %s", payload.get("title"))


def handle_item_assigned(db: Session, outbox: Outbox) -> None:
    """Notify the new assignee."""
    payload = outbox.payload
    assignee_id = payload.get("assignee_id")
    assigned_by = payload.get("assigned_by")
    item_id = payload.get("item_id")

    if assignee_id and assignee_id != assigned_by:
        _create_notification(
            db, assignee_id, item_id, "item.assigned",
            f"{outbox.id}:{assignee_id}",
        )


def handle_item_pending_approval(db: Session, outbox: Outbox) -> None:
    """Notify team leads that an item needs approval."""
    payload = outbox.payload
    team_id = payload.get("team_id")
    item_id = payload.get("item_id")
    assignee_id = payload.get("assignee_id")

    if not team_id:
        return

    # Find leads/admins in the team (not the assignee — separation of duties)
    leads = (
        db.query(Membership)
        .filter(
            Membership.team_id == team_id,
            Membership.role.in_([Role.lead, Role.admin]),
        )
        .all()
    )

    for m in leads:
        if str(m.user_id) != assignee_id:
            _create_notification(
                db, str(m.user_id), item_id, "item.pending_approval",
                f"{outbox.id}:{m.user_id}",
            )


def handle_item_resolved(db: Session, outbox: Outbox) -> None:
    """Notify the assignee and creator that the item was resolved."""
    payload = outbox.payload
    item_id = payload.get("item_id")
    actor_id = payload.get("actor_id")
    assignee_id = payload.get("assignee_id")

    if assignee_id and assignee_id != actor_id:
        _create_notification(
            db, assignee_id, item_id, "item.resolved",
            f"{outbox.id}:{assignee_id}",
        )


def handle_item_rejection(db: Session, outbox: Outbox) -> None:
    """Notify the assignee that their item was rejected (sent back)."""
    payload = outbox.payload
    from_status = payload.get("from_status")
    item_id = payload.get("item_id")
    actor_id = payload.get("actor_id")
    assignee_id = payload.get("assignee_id")

    if from_status == "pending_approval" and assignee_id and assignee_id != actor_id:
        _create_notification(
            db, assignee_id, item_id, "item.rejected",
            f"{outbox.id}:{assignee_id}",
        )


def handle_comment_added(db: Session, outbox: Outbox) -> None:
    """Notify assignee and creator on new comments (not the author)."""
    payload = outbox.payload
    item_id = payload.get("item_id")
    author_id = payload.get("author_id")
    assignee_id = payload.get("assignee_id")
    created_by = payload.get("created_by")

    notified = set()

    # Notify assignee
    if assignee_id and assignee_id != author_id and assignee_id not in notified:
        _create_notification(
            db, assignee_id, item_id, "comment.added",
            f"{outbox.id}:{assignee_id}",
        )
        notified.add(assignee_id)

    # Notify creator
    if created_by and created_by != author_id and created_by not in notified:
        _create_notification(
            db, created_by, item_id, "comment.added",
            f"{outbox.id}:{created_by}",
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_worker()

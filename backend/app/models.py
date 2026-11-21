"""
SQLAlchemy models — the single source of truth for the schema.

Alembic migrations are generated from these models via `alembic revision --autogenerate`.
Database-level constraints (CHECK, triggers, partial indexes) are defined here
and in the Alembic migration for anything SQLAlchemy can't express directly.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import relationship

from app.db import Base


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"


@compiles(TSVECTOR, "sqlite")
def _compile_tsvector_sqlite(type_, compiler, **kw):
    return "TEXT"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Role(str, enum.Enum):
    viewer = "viewer"
    member = "member"
    lead = "lead"
    admin = "admin"


class ItemStatus(str, enum.Enum):
    open = "open"
    in_progress = "in_progress"
    pending_approval = "pending_approval"
    resolved = "resolved"
    closed = "closed"


class ItemPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class OutboxStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    done = "done"
    failed = "failed"


# ---------------------------------------------------------------------------
# Users & Teams
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    memberships = relationship("Membership", back_populates="user", lazy="selectin")
    sessions = relationship("SessionModel", back_populates="user")


class Team(Base):
    __tablename__ = "teams"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)

    memberships = relationship("Membership", back_populates="team", lazy="selectin")


class Membership(Base):
    __tablename__ = "memberships"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    team_id = Column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    role: Column = Column(Enum(Role, name="role_enum"), nullable=False, default=Role.member)

    user = relationship("User", back_populates="memberships")
    team = relationship("Team", back_populates="memberships")

    __table_args__ = (
        Index("ix_memberships_team_role", "team_id", "role"),
    )


# ---------------------------------------------------------------------------
# Sessions (server-side, token hash stored)
# ---------------------------------------------------------------------------

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash = Column(String(128), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="sessions")


# ---------------------------------------------------------------------------
# Work Items
# ---------------------------------------------------------------------------

class WorkItem(Base):
    __tablename__ = "work_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    team_id = Column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status: Column = Column(
        Enum(ItemStatus, name="item_status_enum"),
        nullable=False,
        default=ItemStatus.open,
    )
    priority: Column = Column(
        Enum(ItemPriority, name="item_priority_enum"),
        nullable=False,
        default=ItemPriority.medium,
    )
    assignee_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    requires_approval = Column(Boolean, default=False, nullable=False)
    approved_by = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True)
    version = Column(Integer, nullable=False, default=1)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    search_vector = Column(TSVECTOR)

    team = relationship("Team")
    assignee = relationship("User", foreign_keys=[assignee_id])
    creator = relationship("User", foreign_keys=[created_by])
    approver = relationship("User", foreign_keys=[approved_by])
    events = relationship("ItemEvent", back_populates="item", order_by="ItemEvent.id.desc()")
    comments = relationship("Comment", back_populates="item", order_by="Comment.created_at.desc()")

    __table_args__ = (
        # An in-progress item must have an assignee
        CheckConstraint(
            "status != 'in_progress' OR assignee_id IS NOT NULL",
            name="ck_in_progress_needs_assignee",
        ),
        # Main list query index
        Index(
            "ix_work_items_team_list",
            "team_id", "status", "priority", "updated_at", "id",
        ),
        # "My work" index
        Index("ix_work_items_assignee_status", "assignee_id", "status"),
        # Partial index for open items (keeps the hot index small)
        Index(
            "ix_work_items_open",
            "team_id", "status", "priority", "updated_at",
            postgresql_where="status NOT IN ('resolved', 'closed')",
        ),
        # Full-text search
        Index("ix_work_items_search", "search_vector", postgresql_using="gin"),
    )


# ---------------------------------------------------------------------------
# Item Events (append-only audit log)
# ---------------------------------------------------------------------------

class ItemEvent(Base):
    __tablename__ = "item_events"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    item_id = Column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    actor_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    type = Column(String(50), nullable=False)
    payload = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    item = relationship("WorkItem", back_populates="events")
    actor = relationship("User")

    __table_args__ = (
        Index("ix_item_events_item_id_desc", "item_id", id.desc()),
    )


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class Comment(Base):
    __tablename__ = "comments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    item_id = Column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False
    )
    author_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=False
    )
    body = Column(Text, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    item = relationship("WorkItem", back_populates="comments")
    author = relationship("User")


# ---------------------------------------------------------------------------
# Idempotency Keys
# ---------------------------------------------------------------------------

class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    key = Column(String(100), primary_key=True)
    endpoint = Column(String(200), nullable=False)
    request_hash = Column(String(64), nullable=False)
    status_code = Column(Integer, nullable=False)
    response_body = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Outbox (transactional outbox for async processing)
# ---------------------------------------------------------------------------

class Outbox(Base):
    __tablename__ = "outbox"

    id = Column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    status: Column = Column(
        Enum(OutboxStatus, name="outbox_status_enum"),
        nullable=False,
        default=OutboxStatus.pending,
    )
    attempts = Column(Integer, nullable=False, default=0)
    next_attempt_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    locked_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_outbox_poll", "status", "next_attempt_at"),
    )


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id = Column(
        UUID(as_uuid=True), ForeignKey("work_items.id", ondelete="CASCADE"), nullable=True
    )
    kind = Column(String(100), nullable=False)
    dedupe_key = Column(String(255), unique=True, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User")
    item = relationship("WorkItem")

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "read_at"),
    )

"""Initial schema with all tables, constraints, indexes, and triggers.

Revision ID: 001
Revises: None
Create Date: 2026-10-19
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Enums ---
    op.execute("CREATE TYPE role_enum AS ENUM ('viewer', 'member', 'lead', 'admin')")
    op.execute(
        "CREATE TYPE item_status_enum AS ENUM ('open', 'in_progress', 'pending_approval', 'resolved', 'closed')"
    )
    op.execute("CREATE TYPE item_priority_enum AS ENUM ('low', 'medium', 'high', 'critical')")
    op.execute("CREATE TYPE outbox_status_enum AS ENUM ('pending', 'processing', 'done', 'failed')")

    role_enum = sa.Enum("viewer", "member", "lead", "admin", name="role_enum", create_type=False)
    item_status_enum = sa.Enum(
        "open", "in_progress", "pending_approval", "resolved", "closed",
        name="item_status_enum",
        create_type=False,
    )
    item_priority_enum = sa.Enum("low", "medium", "high", "critical", name="item_priority_enum", create_type=False)
    outbox_status_enum = sa.Enum("pending", "processing", "done", "failed", name="outbox_status_enum", create_type=False)

    # --- Users ---
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # --- Teams ---
    op.create_table(
        "teams",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
    )

    # --- Memberships ---
    op.create_table(
        "memberships",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", role_enum, nullable=False, server_default="member"),
    )
    op.create_index("ix_memberships_team_role", "memberships", ["team_id", "role"])

    # --- Sessions ---
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(128), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"])

    # --- Work Items ---
    op.create_table(
        "work_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("team_id", UUID(as_uuid=True), sa.ForeignKey("teams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", item_status_enum, nullable=False, server_default="open"),
        sa.Column("priority", item_priority_enum, nullable=False, server_default="medium"),
        sa.Column("assignee_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("requires_approval", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("search_vector", TSVECTOR()),
        # CHECK: in_progress items must have an assignee
        sa.CheckConstraint(
            "status != 'in_progress' OR assignee_id IS NOT NULL",
            name="ck_in_progress_needs_assignee",
        ),
    )

    # Indexes
    op.create_index("ix_work_items_team_list", "work_items", ["team_id", "status", "priority", "updated_at", "id"])
    op.create_index("ix_work_items_assignee_status", "work_items", ["assignee_id", "status"])
    op.create_index(
        "ix_work_items_open", "work_items",
        ["team_id", "status", "priority", "updated_at"],
        postgresql_where=sa.text("status NOT IN ('resolved', 'closed')"),
    )
    op.create_index("ix_work_items_search", "work_items", ["search_vector"], postgresql_using="gin")

    # Trigger to auto-update search_vector on insert/update
    op.execute("""
        CREATE OR REPLACE FUNCTION work_items_search_trigger() RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('english', coalesce(NEW.title, '') || ' ' || coalesce(NEW.description, ''));
            RETURN NEW;
        END
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_work_items_search
        BEFORE INSERT OR UPDATE OF title, description ON work_items
        FOR EACH ROW EXECUTE FUNCTION work_items_search_trigger();
    """)

    # --- Item Events (append-only) ---
    op.create_table(
        "item_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_item_events_item_id_desc", "item_events", ["item_id", sa.text("id DESC")])

    # Append-only trigger: reject UPDATE and DELETE on item_events
    op.execute("""
        CREATE OR REPLACE FUNCTION prevent_item_events_modification() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'item_events is append-only: % operations are not allowed', TG_OP;
        END
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trg_item_events_no_update
        BEFORE UPDATE ON item_events
        FOR EACH ROW EXECUTE FUNCTION prevent_item_events_modification();

        CREATE TRIGGER trg_item_events_no_delete
        BEFORE DELETE ON item_events
        FOR EACH ROW EXECUTE FUNCTION prevent_item_events_modification();
    """)

    # --- Comments ---
    op.create_table(
        "comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Idempotency Keys ---
    op.create_table(
        "idempotency_keys",
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("endpoint", sa.String(200), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column("response_body", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    # --- Outbox ---
    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("type", sa.String(100), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", outbox_status_enum, nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_outbox_poll", "outbox", ["status", "next_attempt_at"])

    # --- Notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_id", UUID(as_uuid=True), sa.ForeignKey("work_items.id", ondelete="CASCADE"), nullable=True),
        sa.Column("kind", sa.String(100), nullable=False),
        sa.Column("dedupe_key", sa.String(255), unique=True, nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_notifications_user_unread", "notifications", ["user_id", "read_at"])


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("outbox")
    op.drop_table("idempotency_keys")
    op.drop_table("comments")

    op.execute("DROP TRIGGER IF EXISTS trg_item_events_no_delete ON item_events")
    op.execute("DROP TRIGGER IF EXISTS trg_item_events_no_update ON item_events")
    op.execute("DROP FUNCTION IF EXISTS prevent_item_events_modification()")
    op.drop_table("item_events")

    op.execute("DROP TRIGGER IF EXISTS trg_work_items_search ON work_items")
    op.execute("DROP FUNCTION IF EXISTS work_items_search_trigger()")
    op.drop_table("work_items")

    op.drop_table("sessions")
    op.drop_table("memberships")
    op.drop_table("teams")
    op.drop_table("users")

    op.execute("DROP TYPE IF EXISTS outbox_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS item_priority_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS item_status_enum CASCADE")
    op.execute("DROP TYPE IF EXISTS role_enum CASCADE")

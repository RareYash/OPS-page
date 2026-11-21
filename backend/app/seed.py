"""
Seed script — populates the database with demo data.

Creates 3 teams, ~8 users with mixed roles, and sample work items.
Use --large flag to generate 50,000 items for performance testing.

Usage:
    python -m app.seed          # Standard seed (~20 items)
    python -m app.seed --large  # Performance seed (50,000 items)
"""

import random
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from app.db import Base, SessionLocal, engine
from app.models import (
    ItemEvent,
    ItemPriority,
    ItemStatus,
    Membership,
    Role,
    Team,
    User,
    WorkItem,
)
from app.security import hash_password

# ---------------------------------------------------------------------------
# Demo data
# ---------------------------------------------------------------------------

TEAMS = [
    {"name": "Platform Engineering", "slug": "platform"},
    {"name": "Product Team", "slug": "product"},
    {"name": "Security & Compliance", "slug": "security"},
]

USERS = [
    # (email, name, password)
    ("alice@example.com", "Alice Chen", "password123"),
    ("bob@example.com", "Bob Patel", "password123"),
    ("charlie@example.com", "Charlie Kim", "password123"),
    ("diana@example.com", "Diana Müller", "password123"),
    ("ethan@example.com", "Ethan Osei", "password123"),
    ("faye@example.com", "Faye Nakamura", "password123"),
    ("george@example.com", "George Torres", "password123"),
    ("hana@example.com", "Hana Al-Rashid", "password123"),
]

# user_email → {team_slug: role}
MEMBERSHIPS = {
    "alice@example.com": {"platform": "admin", "product": "viewer"},
    "bob@example.com": {"platform": "lead", "security": "member"},
    "charlie@example.com": {"platform": "member", "product": "member"},
    "diana@example.com": {"product": "admin", "security": "lead"},
    "ethan@example.com": {"product": "member"},
    "faye@example.com": {"platform": "member", "product": "lead"},
    "george@example.com": {"security": "admin", "platform": "viewer"},
    "hana@example.com": {"security": "member", "product": "member"},
}

SAMPLE_TITLES = [
    "Fix database connection pooling",
    "Update API rate limiting configuration",
    "Implement user onboarding flow",
    "Review security audit findings",
    "Optimize query performance for dashboard",
    "Add pagination to item list endpoint",
    "Configure CORS headers for production",
    "Write integration tests for claim workflow",
    "Set up monitoring alerts for worker",
    "Document API authentication flow",
    "Migrate legacy data to new schema",
    "Fix timezone handling in notifications",
    "Add health check for worker process",
    "Implement search indexing pipeline",
    "Review and update dependency versions",
    "Add request logging middleware",
    "Fix race condition in assignment flow",
    "Configure backup and recovery procedures",
    "Implement session cleanup job",
    "Add metrics endpoint for observability",
]


def seed(large: bool = False):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        # Check if already seeded
        existing = db.query(User).first()
        if existing:
            print("Database already seeded. Truncate tables first to re-seed.")
            print("  Run: docker compose exec db psql -U newtonite -d newtonite -c 'TRUNCATE users, teams CASCADE'")
            return

        print("Seeding database...")

        # Create teams
        teams = {}
        for t in TEAMS:
            team = Team(name=t["name"], slug=t["slug"])
            db.add(team)
            db.flush()
            teams[t["slug"]] = team
        print(f"  Created {len(teams)} teams")

        # Create users
        users = {}
        for email, name, password in USERS:
            user = User(
                email=email.lower(),
                name=name,
                password_hash=hash_password(password),
            )
            db.add(user)
            db.flush()
            users[email] = user
        print(f"  Created {len(users)} users")

        # Create memberships
        membership_count = 0
        for email, team_roles in MEMBERSHIPS.items():
            user = users[email]
            for slug, role in team_roles.items():
                team = teams[slug]
                m = Membership(user_id=user.id, team_id=team.id, role=Role(role))
                db.add(m)
                membership_count += 1
        db.flush()
        print(f"  Created {membership_count} memberships")

        # Create work items
        item_count = 50000 if large else 20
        print(f"  Creating {item_count} work items...")

        statuses = list(ItemStatus)
        priorities = list(ItemPriority)
        team_list = list(teams.values())

        for i in range(item_count):
            team = random.choice(team_list)

            # Get team members (not viewers)
            team_members = [
                users[email]
                for email, roles in MEMBERSHIPS.items()
                if str(team.slug) in roles and roles[str(team.slug)] != "viewer"
            ]

            if not team_members:
                continue

            creator = random.choice(team_members)
            status = random.choice(statuses)
            priority = random.choice(priorities)

            # Assign if in_progress or later
            assignee = None
            if status != ItemStatus.open:
                assignee = random.choice(team_members)

            title = random.choice(SAMPLE_TITLES)
            if large:
                title = f"{title} (#{i + 1})"

            now = datetime.now(timezone.utc)
            created_at = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            due_at = None
            if random.random() < 0.4:
                due_at = created_at + timedelta(days=random.randint(1, 14))

            item = WorkItem(
                team_id=team.id,
                title=title[:200],
                description=f"Auto-generated seed item #{i + 1}" if large else f"Description for: {title}",
                status=status,
                priority=priority,
                assignee_id=assignee.id if assignee else None,
                created_by=creator.id,
                requires_approval=random.random() < 0.3,
                due_at=due_at,
                created_at=created_at,
                updated_at=created_at + timedelta(hours=random.randint(0, 48)),
            )
            db.add(item)

            if i % 1000 == 0 and i > 0:
                db.flush()
                print(f"    ... {i} items created")

        db.flush()

        # Update search vectors for all items (PostgreSQL)
        if db.bind and db.bind.dialect.name != "sqlite":
            db.execute(text(
                "UPDATE work_items SET search_vector = "
                "to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, ''))"
            ))

        # Add some events for the first few items
        items = db.query(WorkItem).limit(20).all()
        for item in items:
            _add_event(db, item.id, item.created_by, "item.created", {
                "title": item.title,
            })
            if item.assignee_id:
                _add_event(db, item.id, item.created_by, "item.assigned", {
                    "assignee_id": str(item.assignee_id),
                })

        db.commit()

        print(f"\n[OK] Seed complete: {len(teams)} teams, {len(users)} users, {item_count} items")
        print("\nDemo accounts (all passwords: password123):")
        print("  +-----------------------------+------------------------------------------+")
        print("  | Email                       | Roles                                    |")
        print("  +-----------------------------+------------------------------------------+")
        for email, roles in MEMBERSHIPS.items():
            role_str = ", ".join(f"{slug}:{role}" for slug, role in roles.items())
            print(f"  | {email:<27} | {role_str:<40} |")
        print("  +-----------------------------+------------------------------------------+")
        print("\n[!] Demo-only passwords. Do not use in production.")

    except Exception as e:
        db.rollback()
        print(f"Error seeding: {e}")
        raise
    finally:
        db.close()


def _add_event(db, item_id, actor_id, event_type, payload):
    event = ItemEvent(
        item_id=item_id,
        actor_id=actor_id,
        type=event_type,
        payload=payload,
    )
    db.add(event)
    db.flush()


if __name__ == "__main__":
    large = "--large" in sys.argv
    seed(large=large)

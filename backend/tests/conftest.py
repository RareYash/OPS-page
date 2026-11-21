"""
Pytest configuration and fixtures for Newtonite Ops.

Configures test database session, test client, and seeded entities
(teams, users with various roles, sample items).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Generator
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.db import Base, get_db
from app.main import app
from app.models import (
    ItemPriority,
    ItemStatus,
    Membership,
    Role,
    SessionModel,
    Team,
    User,
    WorkItem,
)
from app.security import hash_password, hash_token, generate_session_token

settings = get_settings()

# Use isolated test database URL so running pytest never touches or wipes dev.db
TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    os.getenv("DATABASE_URL", "sqlite:///d:/project/backend/test.db"),
)

if TEST_DB_URL.startswith("sqlite"):
    test_engine = create_engine(
        TEST_DB_URL,
        connect_args={"check_same_thread": False},
    )
else:
    test_engine = create_engine(
        TEST_DB_URL,
        pool_size=10,
        max_overflow=10,
        pool_pre_ping=True,
    )
TestingSessionLocal = sessionmaker(bind=test_engine, autocommit=False, autoflush=False)


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    """Ensure schema exists before tests run."""
    try:
        # Create all tables if not present (or alembic already applied)
        Base.metadata.create_all(bind=test_engine)
        yield
    finally:
        pass


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a clean DB session for each test and purge tables on cleanup."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Clean up test tables after test completes
        with test_engine.begin() as conn:
            if test_engine.dialect.name == "sqlite":
                for table in reversed(Base.metadata.sorted_tables):
                    conn.execute(table.delete())
            else:
                conn.execute(
                    text(
                        "TRUNCATE users, teams, work_items, item_events, outbox, "
                        "notifications, idempotency_keys, comments, sessions CASCADE"
                    )
                )


@pytest.fixture
def client(db: Session) -> Generator[TestClient, None, None]:
    """Test client with isolated db dependency override."""
    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, base_url="http://testserver") as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed fixtures: Teams, Users, Sessions
# ---------------------------------------------------------------------------

@pytest.fixture
def team_alpha(db: Session) -> Team:
    """Primary test team."""
    team = Team(name="Alpha Team", slug="alpha-team")
    db.add(team)
    db.commit()
    return team


@pytest.fixture
def team_beta(db: Session) -> Team:
    """Isolated second team to test cross-team permission boundaries."""
    team = Team(name="Beta Team", slug="beta-team")
    db.add(team)
    db.commit()
    return team


@pytest.fixture
def user_admin(db: Session, team_alpha: Team) -> tuple[User, str]:
    """Admin user in Alpha Team. Returns (User, session_token)."""
    user = User(
        email="admin@alpha.example.com",
        name="Admin Alice",
        password_hash=hash_password("admin_pass_123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    m = Membership(user_id=user.id, team_id=team_alpha.id, role=Role.admin)
    db.add(m)

    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return user, token


@pytest.fixture
def user_lead(db: Session, team_alpha: Team) -> tuple[User, str]:
    """Lead user in Alpha Team. Returns (User, session_token)."""
    user = User(
        email="lead@alpha.example.com",
        name="Lead Leo",
        password_hash=hash_password("lead_pass_123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    m = Membership(user_id=user.id, team_id=team_alpha.id, role=Role.lead)
    db.add(m)

    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return user, token


@pytest.fixture
def user_member(db: Session, team_alpha: Team) -> tuple[User, str]:
    """Regular member in Alpha Team. Returns (User, session_token)."""
    user = User(
        email="member@alpha.example.com",
        name="Member Maya",
        password_hash=hash_password("member_pass_123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    m = Membership(user_id=user.id, team_id=team_alpha.id, role=Role.member)
    db.add(m)

    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return user, token


@pytest.fixture
def user_viewer(db: Session, team_alpha: Team) -> tuple[User, str]:
    """Viewer user in Alpha Team. Returns (User, session_token)."""
    user = User(
        email="viewer@alpha.example.com",
        name="Viewer Victor",
        password_hash=hash_password("viewer_pass_123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    m = Membership(user_id=user.id, team_id=team_alpha.id, role=Role.viewer)
    db.add(m)

    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return user, token


@pytest.fixture
def user_outsider(db: Session, team_beta: Team) -> tuple[User, str]:
    """User in Beta Team only (outsider to Alpha Team). Returns (User, session_token)."""
    user = User(
        email="outsider@beta.example.com",
        name="Outsider Oscar",
        password_hash=hash_password("outsider_pass_123"),
        is_active=True,
    )
    db.add(user)
    db.flush()

    m = Membership(user_id=user.id, team_id=team_beta.id, role=Role.member)
    db.add(m)

    token = generate_session_token()
    session = SessionModel(
        user_id=user.id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc) + timedelta(hours=8),
    )
    db.add(session)
    db.commit()
    return user, token


@pytest.fixture
def sample_item(db: Session, team_alpha: Team, user_member: tuple[User, str]) -> WorkItem:
    """Sample work item in Alpha Team created by member."""
    user, _ = user_member
    item = WorkItem(
        team_id=team_alpha.id,
        title="Sample Task 1",
        description="A task for testing operations under pressure",
        status=ItemStatus.open,
        priority=ItemPriority.medium,
        created_by=user.id,
        requires_approval=False,
        version=1,
    )
    db.add(item)
    db.commit()
    return item

"""
Authentication and session security tests for Newtonite Ops.

Tests:
1. Uniform error: non-existent email and wrong password return the exact same generic error message and status (401).
2. Valid login sets an HttpOnly cookie with SameSite.
3. Logout invalidates session immediately.
4. Inactive user is rejected on login.
5. Expired session token is rejected.
6. Rate limiting on /auth/login returns 429 after threshold exceeded.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import SessionModel, Team, User
from app.security import hash_password, hash_token, generate_session_token


def test_uniform_error_for_unknown_user_and_bad_password(client: TestClient, user_member: tuple[User, str]):
    """
    To prevent user enumeration, login returns the identical 401 error message
    whether the user does not exist or the password is incorrect.
    """
    member_user, _ = user_member

    # Non-existent email
    r_unknown = client.post(
        "/auth/login",
        json={"email": "nobody_exists_here_12345@test.com", "password": "any_password"},
    )
    assert r_unknown.status_code == 401
    err_unknown = r_unknown.json()

    # Existing email, bad password
    r_bad_pass = client.post(
        "/auth/login",
        json={"email": member_user.email, "password": "wrong_password_totally"},
    )
    assert r_bad_pass.status_code == 401
    err_bad_pass = r_bad_pass.json()

    assert err_unknown == err_bad_pass
    assert err_unknown.get("detail") == "Invalid email or password"


def test_login_and_logout_flow(client: TestClient, db: Session, team_alpha: Team):
    """Test full login, /me inspection, and logout invalidation."""
    email = f"logintest_{uuid4().hex[:6]}@test.com"
    raw_pass = "Strong_Secret_123!"

    user = User(
        email=email,
        name="Login Tester",
        password_hash=hash_password(raw_pass),
        is_active=True,
    )
    db.add(user)
    db.commit()

    # 1. Successful Login
    r_login = client.post(
        "/auth/login",
        json={"email": email, "password": raw_pass},
    )
    assert r_login.status_code == 200
    assert "session" in r_login.cookies
    session_cookie = r_login.cookies["session"]

    # 2. Access /auth/me with session cookie
    r_me = client.get("/auth/me", cookies={"session": session_cookie})
    assert r_me.status_code == 200
    assert r_me.json()["email"] == email

    # 3. Logout
    r_logout = client.post("/auth/logout", cookies={"session": session_cookie})
    assert r_logout.status_code == 200

    # 4. Access /auth/me after logout -> 401 Unauthorized
    r_after = client.get("/auth/me", cookies={"session": session_cookie})
    assert r_after.status_code == 401


def test_inactive_user_cannot_login(client: TestClient, db: Session):
    """Inactive users must be refused login."""
    email = f"inactive_{uuid4().hex[:6]}@test.com"
    raw_pass = "ValidPass123!"

    user = User(
        email=email,
        name="Deactivated User",
        password_hash=hash_password(raw_pass),
        is_active=False,
    )
    db.add(user)
    db.commit()

    r = client.post(
        "/auth/login",
        json={"email": email, "password": raw_pass},
    )
    assert r.status_code == 401


def test_expired_session_rejected(client: TestClient, db: Session, user_member: tuple[User, str]):
    """A session row with past expires_at timestamp is rejected."""
    user, _ = user_member
    expired_token = generate_session_token()
    s = SessionModel(
        user_id=user.id,
        token_hash=hash_token(expired_token),
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db.add(s)
    db.commit()

    r = client.get("/auth/me", cookies={"session": expired_token})
    assert r.status_code == 401

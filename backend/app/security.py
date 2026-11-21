"""
Security utilities: password hashing, session management, CSRF/origin checks.

- argon2id for password hashing (not bcrypt, not SHA)
- Server-side sessions with hashed tokens
- Cookie config: HttpOnly, SameSite=Lax, Secure in prod
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import SessionModel, User

ph = PasswordHasher()
settings = get_settings()


def hash_password(password: str) -> str:
    """Hash a password using argon2id."""
    return ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against an argon2id hash."""
    try:
        return ph.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def generate_session_token() -> str:
    """Generate a cryptographically random session token."""
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    """
    Hash a session token for storage.
    We use SHA-256 since the token itself is high-entropy;
    argon2 would be overkill and slow for session lookups.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user_id: UUID, token: str) -> SessionModel:
    """Create a new server-side session."""
    session = SessionModel(
        user_id=user_id,
        token_hash=hash_token(token),
        expires_at=datetime.now(timezone.utc)
        + timedelta(hours=settings.session_expire_hours),
    )
    db.add(session)
    db.flush()
    return session


def delete_session(db: Session, token: str) -> None:
    """Invalidate a session by deleting it."""
    token_h = hash_token(token)
    session = db.execute(
        select(SessionModel).where(SessionModel.token_hash == token_h)
    ).scalar_one_or_none()
    if session:
        db.delete(session)
        db.flush()


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    session_token: str | None = Cookie(default=None, alias="session"),
) -> User:
    """
    FastAPI dependency: extracts the current authenticated user from the session cookie.
    Raises 401 if not authenticated. Checks session expiry and user active status.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token_h = hash_token(session_token)
    session = db.execute(
        select(SessionModel)
        .where(SessionModel.token_hash == token_h)
        .where(SessionModel.expires_at > datetime.now(timezone.utc))
    ).scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Account inactive or not found")

    # Store user on request for easy access
    request.state.user = user
    return user


def get_user_team_role(user: User, team_id: UUID) -> str | None:
    """Get the user's role in a specific team, or None if not a member."""
    for m in user.memberships:
        if m.team_id == team_id:
            return m.role.value if hasattr(m.role, "value") else m.role
    return None


def check_csrf(request: Request) -> None:
    """
    CSRF defense for cookie-based auth:
    State-changing requests must include X-Requested-With header.
    Origin header is also checked against the allow-list.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Require custom header (AJAX-only protection)
    if not request.headers.get("X-Requested-With"):
        raise HTTPException(status_code=403, detail="Missing X-Requested-With header")

    # Check Origin if present
    origin = request.headers.get("Origin")
    if origin:
        allowed = settings.allowed_origins_list
        if origin not in allowed:
            raise HTTPException(
                status_code=403, detail="Origin not allowed"
            )

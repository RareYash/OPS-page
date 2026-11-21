"""
Auth router — login, logout, current user.

- Same error message for unknown user and wrong password
- Rate limiting on login (per IP)
- Session cookie: HttpOnly, SameSite=Lax, Secure in prod
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.models import User
from app.schemas import LoginRequest, MeResponse, TeamMembershipResponse, UserResponse
from app.security import (
    create_session,
    delete_session,
    generate_session_token,
    get_current_user,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

# Simple in-memory rate limiter for login (per IP)
# In production, this would be distributed (Redis or DB-backed)
_login_attempts: dict[str, list[float]] = {}


def _check_rate_limit(client_ip: str) -> None:
    """Rate limit login attempts per IP."""
    now = datetime.now(timezone.utc).timestamp()
    window = 60  # 1 minute window
    limit = settings.login_rate_limit_per_minute

    attempts = _login_attempts.get(client_ip, [])
    # Remove old attempts
    attempts = [t for t in attempts if now - t < window]
    _login_attempts[client_ip] = attempts

    if len(attempts) >= limit:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Please try again later.",
        )


@router.post("/login")
def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Authenticate and create a session.
    Returns the same error for wrong password and unknown user.
    """
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    # Record the attempt
    now = datetime.now(timezone.utc).timestamp()
    _login_attempts.setdefault(client_ip, []).append(now)

    # Find user by email (case-insensitive)
    user = db.execute(
        select(User).where(func.lower(User.email) == body.email.lower())
    ).scalar_one_or_none()

    # Same error for unknown user and wrong password
    invalid_msg = "Invalid email or password"

    if not user:
        raise HTTPException(status_code=401, detail=invalid_msg)

    if not user.is_active:
        raise HTTPException(status_code=401, detail=invalid_msg)

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail=invalid_msg)

    # Create session
    token = generate_session_token()
    create_session(db, user.id, token)

    # Set cookie
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        secure=not settings.is_dev,
        max_age=settings.session_expire_hours * 3600,
        path="/",
    )

    return {"message": "Logged in", "user": UserResponse.model_validate(user)}


@router.post("/logout")
def logout(
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logout: delete the server-side session and clear the cookie."""
    session_token = request.cookies.get("session")
    if session_token:
        delete_session(db, session_token)

    response.delete_cookie(key="session", path="/")
    return {"message": "Logged out"}


@router.get("/me", response_model=MeResponse)
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get the current user's profile including team memberships."""
    teams = []
    for m in user.memberships:
        teams.append(
            TeamMembershipResponse(
                team_id=m.team_id,
                team_name=m.team.name,
                team_slug=m.team.slug,
                role=m.role.value if hasattr(m.role, "value") else m.role,
            )
        )

    return MeResponse(
        id=user.id,
        email=user.email,
        name=user.name,
        is_active=user.is_active,
        created_at=user.created_at,
        teams=teams,
    )

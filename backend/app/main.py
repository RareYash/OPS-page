"""
Newtonite Ops — FastAPI application entry point.

- Global exception handler: generic message + request ID, no stack traces
- CORS configured from allow-list
- Security headers on all responses
- Request body size limit
"""

import uuid
import logging
import traceback

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.routers import auth, items, dashboard, notifications

settings = get_settings()

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("y_corp")

app = FastAPI(
    title="Y corp. Ops",
    description="Y corp. Operations Under Pressure — Work Item Tracking System",
    version="1.0.0",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url=None,
)

# CORS — explicit origin list, not "*"
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id", "X-Current-Version"],
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MAX_BODY_SIZE = 1_048_576  # 1 MB


@app.middleware("http")
async def add_request_id_and_security_headers(request: Request, call_next):
    """Add request ID, security headers, and body size check."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Body size limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_SIZE:
        return JSONResponse(
            status_code=413,
            content={"error": {"code": "body_too_large", "message": "Request body too large", "request_id": request_id}},
        )

    response: Response = await call_next(request)

    # Request ID header
    response.headers["X-Request-Id"] = request_id

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; "
        "frame-ancestors 'none'"
    )

    return response


# ---------------------------------------------------------------------------
# Global exception handler
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Catch-all exception handler.
    Returns a generic message + request ID to the client.
    Full details go only to server logs.
    """
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "Unhandled exception [request_id=%s]: %s\n%s",
        request_id,
        str(exc),
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "An internal error occurred. Please try again.",
                "request_id": request_id,
            }
        },
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

app.include_router(auth.router)
app.include_router(items.router)
app.include_router(dashboard.router)
app.include_router(notifications.router)


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "y-corp-ops"}


@app.get("/teams")
def list_teams(request: Request):
    """List teams the current user belongs to (requires auth)."""
    from app.db import SessionLocal
    from app.schemas import TeamResponse

    # This is a simple endpoint so we handle it inline
    db = SessionLocal()
    try:
        session_token = request.cookies.get("session")
        if not session_token:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "Not authenticated"}})

        from app.security import hash_token
        from app.models import SessionModel, User
        from sqlalchemy import select
        from datetime import datetime, timezone

        token_h = hash_token(session_token)
        session = db.execute(
            select(SessionModel)
            .where(SessionModel.token_hash == token_h)
            .where(SessionModel.expires_at > datetime.now(timezone.utc))
        ).scalar_one_or_none()

        if not session:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "Session expired"}})

        user = db.get(User, session.user_id)
        if not user or not user.is_active:
            return JSONResponse(status_code=401, content={"error": {"code": "unauthorized", "message": "Account inactive"}})

        teams = []
        for m in user.memberships:
            teams.append(TeamResponse(
                id=m.team.id,
                name=m.team.name,
                slug=m.team.slug,
                my_role=m.role.value if hasattr(m.role, "value") else m.role,
            ))

        return [t.model_dump(mode="json") for t in teams]
    finally:
        db.close()

"""
Idempotency key middleware.

Handles the Idempotency-Key header for POST requests:
- Same key + same request hash → replay stored response
- Same key + different body → 422
- New key → proceed, store response in same transaction
- Keys expire after 24 hours
"""

import hashlib
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import IdempotencyKey


def compute_request_hash(endpoint: str, body: bytes) -> str:
    """Hash the endpoint + request body for comparison."""
    content = f"{endpoint}:{body.decode('utf-8', errors='replace')}"
    return hashlib.sha256(content.encode()).hexdigest()


def check_idempotency(
    db: Session,
    user_id: UUID,
    key: str,
    endpoint: str,
    request_hash: str,
) -> dict | None:
    """
    Check if this idempotency key has been used before.
    Returns the stored response if it's a replay, None if it's a new request.
    Raises 422 if the key was used with a different body.
    """
    existing = db.execute(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.key == key,
        )
    ).scalar_one_or_none()

    if existing is None:
        return None

    if existing.request_hash != request_hash:
        raise HTTPException(
            status_code=422,
            detail="Idempotency key already used with a different request body",
        )

    # Replay the stored response
    return {
        "status_code": existing.status_code,
        "body": existing.response_body,
    }


def store_idempotency_response(
    db: Session,
    user_id: UUID,
    key: str,
    endpoint: str,
    request_hash: str,
    status_code: int,
    response_body: dict,
) -> None:
    """
    Store the response for this idempotency key.
    Called in the same transaction as the business write.
    """
    idem = IdempotencyKey(
        user_id=user_id,
        key=key,
        endpoint=endpoint,
        request_hash=request_hash,
        status_code=status_code,
        response_body=response_body,
    )
    db.add(idem)
    db.flush()

"""
Pydantic schemas for request validation and response serialization.

Rules:
- extra="forbid" on all input schemas (no mass assignment)
- password_hash and session tokens never appear in responses
- Length limits match DB constraints
- Enum values validated by Pydantic
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime
    teams: list["TeamMembershipResponse"] = []


class TeamMembershipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    team_id: UUID
    team_name: str
    team_slug: str
    role: str


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------

class TeamResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    slug: str
    my_role: str | None = None


# ---------------------------------------------------------------------------
# Work Items
# ---------------------------------------------------------------------------

class ItemCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    team_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: str = Field(default="medium", pattern=r"^(low|medium|high|critical)$")
    requires_approval: bool = False
    due_at: datetime | None = None


class ItemUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    priority: str | None = Field(default=None, pattern=r"^(low|medium|high|critical)$")
    requires_approval: bool | None = None
    due_at: datetime | None = None


class ItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    team_id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    assignee_id: UUID | None
    assignee_name: str | None = None
    created_by: UUID
    creator_name: str | None = None
    requires_approval: bool
    approved_by: UUID | None
    approved_at: datetime | None
    due_at: datetime | None
    version: int
    created_at: datetime
    updated_at: datetime
    allowed_actions: list[str] = []


class ItemListResponse(BaseModel):
    items: list[ItemResponse]
    next_cursor: str | None = None
    total_estimate: int | None = None


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

class TransitionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str = Field(pattern=r"^(open|in_progress|pending_approval|resolved|closed)$")
    comment: str | None = Field(default=None, max_length=10000)


class AssignRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignee_id: UUID


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------

class CommentCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    body: str = Field(min_length=1, max_length=10000)


class CommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    item_id: UUID
    author_id: UUID
    author_name: str | None = None
    body: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    item_id: UUID
    actor_id: UUID
    actor_name: str | None = None
    type: str
    payload: dict | None
    created_at: datetime


class EventListResponse(BaseModel):
    events: list[EventResponse]
    next_cursor: str | None = None


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardSection(BaseModel):
    label: str
    items: list[ItemResponse]
    count: int


class DashboardResponse(BaseModel):
    sections: list[DashboardSection]
    status_counts: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    user_id: UUID
    item_id: UUID | None
    kind: str
    read_at: datetime | None
    created_at: datetime


class NotificationListResponse(BaseModel):
    notifications: list[NotificationResponse]
    unread_count: int


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail

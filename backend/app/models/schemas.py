"""Pydantic v2 request/response contracts for the API layer."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------- Sessions ----------

class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    user_metadata: dict = Field(default_factory=dict)


class SessionSummary(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime


class SourceRef(BaseModel):
    episode: str
    guest: str | None = None
    timestamp: str | None = None
    score: float


class MessageOut(BaseModel):
    id: UUID
    role: Literal["user", "assistant", "system"]
    content: str
    sources: list[SourceRef] = Field(default_factory=list)
    provider: str | None = None
    mode: str = "qa"
    created_at: datetime


class SessionDetail(SessionSummary):
    messages: list[MessageOut] = Field(default_factory=list)


# ---------- Chat ----------

class ChatRequest(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=8000)
    mode: Literal["qa", "ship30", "artifact"] = "qa"
    provider: Literal["ollama", "anthropic"] | None = None


# ---------- Errors (RFC-7807-style) ----------

class ErrorResponse(BaseModel):
    type: str
    title: str
    detail: str
    status: int


# ---------- Health ----------

class DependencyStatus(BaseModel):
    name: str
    ok: bool
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "down"]
    dependencies: list[DependencyStatus]

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: str
    email: str
    display_name: str | None
    role: str


class ChatMessageRequest(BaseModel):
    conversation_id: str | None = None
    text: str


class CitedSourceOut(BaseModel):
    source_id: str
    title: str
    video_title: str | None = None
    video_url: str | None = None
    document_url: str | None = None
    start_timestamp: str | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    text: str
    escalated: bool
    cited_sources: list[CitedSourceOut] = []
    retrieval_score: float | None = None


class ConversationSummary(BaseModel):
    id: str
    channel: str
    status: str
    updated_at: datetime


class MessageOut(BaseModel):
    id: str
    direction: str
    kind: str
    body: str | None
    voice_transcript: str | None
    sources_cited: list[dict] | None
    created_at: datetime


class SourceOut(BaseModel):
    id: str
    title: str
    technique: str | None
    origin_filename: str
    origin_kind: str
    version: int
    status: str
    video_url: str | None
    document_url: str | None
    updated_at: datetime


class EscalationOut(BaseModel):
    id: str
    conversation_id: str
    reason: str
    summary: str | None
    status: str
    created_at: datetime


class ResolveEscalationRequest(BaseModel):
    notes: str

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
    video_platform: str | None = None
    video_preview_url: str | None = None
    video_open_url: str | None = None  # video_url, con deep-link al timestamp se la piattaforma lo supporta
    document_url: str | None = None
    start_timestamp: str | None = None


class SuggestedVideoOut(BaseModel):
    """Video indicizzato solo per titolo (nessuna trascrizione): mai un timestamp, per
    costruzione — vedi Luce_Anteprime_Video_Cowork_Specifica, sezione 5."""

    video_id: str
    title: str
    url: str
    platform: str
    preview_url: str | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    message_id: str | None = None  # id del messaggio outbound, per collegare un feedback — assente per notifiche senza un vero messaggio salvato
    text: str
    escalated: bool
    cited_sources: list[CitedSourceOut] = []
    suggested_videos: list[SuggestedVideoOut] = []
    retrieval_score: float | None = None
    transcript: str | None = None  # testo trascritto del messaggio in ingresso, solo per i vocali


class ConversationSummary(BaseModel):
    id: str
    channel: str
    status: str
    updated_at: datetime
    preview: str | None = None  # testo del primo messaggio dell'utente, per distinguere le conversazioni in elenco


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
    video_title: str | None
    video_id: str | None
    document_url: str | None
    updated_at: datetime


class VideoOut(BaseModel):
    id: str
    title: str
    platform: str
    url: str
    technique: str | None
    description: str | None
    preview_url: str | None = None
    subcategory: str | None = None
    tags: str | None = None
    transcript_available: bool = False  # calcolato al volo (Source transcript_csv collegata), non salvato
    timestamps_available: bool = False  # calcolato al volo (quella trascrizione ha almeno un chunk con timestamp)
    updated_at: datetime


class VideoCreateRequest(BaseModel):
    title: str
    url: str
    platform: str = "drive"
    technique_slug: str | None = None
    description: str | None = None
    preview_url: str | None = None
    subcategory: str | None = None
    tags: str | None = None


class VideoUpdateRequest(BaseModel):
    title: str | None = None
    url: str | None = None
    platform: str | None = None
    technique_slug: str | None = None
    description: str | None = None
    preview_url: str | None = None
    subcategory: str | None = None
    tags: str | None = None


class EscalationOut(BaseModel):
    id: str
    conversation_id: str
    reason: str
    summary: str | None
    status: str
    created_at: datetime


class ResolveEscalationRequest(BaseModel):
    notes: str


# I 7 tipi di feedback della Specifica_Definitiva_Tutor_AI, punto 11.
FEEDBACK_TYPES = (
    "mi_e_stata_utile",
    "non_ha_risolto_il_problema",
    "problema_risolto",
    "problema_parzialmente_risolto",
    "problema_non_risolto",
    "risposta_non_corretta",
    "ho_dovuto_contattare_il_tutor",
)


class FeedbackRequest(BaseModel):
    tipo: str
    nota: str | None = None


class FeedbackResponse(BaseModel):
    id: str
    tipo: str
    case_stato: str | None = None
    escalated: bool = False

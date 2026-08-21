import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, JSON, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def _uuid_col():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


class Technique(Base):
    __tablename__ = "techniques"

    id: Mapped[uuid.UUID] = _uuid_col()
    slug: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Video(Base):
    __tablename__ = "videos"

    id: Mapped[uuid.UUID] = _uuid_col()
    title: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, default="drive")
    url: Mapped[str] = mapped_column(String, nullable=False)
    technique_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("techniques.id"))
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    technique: Mapped[Technique | None] = relationship()


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = _uuid_col()
    title: Mapped[str] = mapped_column(String, nullable=False)
    technique_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("techniques.id"))
    video_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("videos.id"))
    document_url: Mapped[str | None] = mapped_column(String)
    origin_filename: Mapped[str] = mapped_column(String, nullable=False)
    origin_kind: Mapped[str] = mapped_column(String, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="active")
    checksum: Mapped[str | None] = mapped_column(String)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="source", cascade="all, delete-orphan")
    technique: Mapped[Technique | None] = relationship()
    video: Mapped[Video | None] = relationship()


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = _uuid_col()
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"))
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_timestamp: Mapped[str | None] = mapped_column(String)
    end_timestamp: Mapped[str | None] = mapped_column(String)
    embedding = mapped_column(Vector(1024))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[Source] = relationship(back_populates="chunks")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = _uuid_col()
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = _uuid_col()
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    channel: Mapped[str] = mapped_column(String, nullable=False)
    external_conversation_id: Mapped[str | None] = mapped_column(String)
    external_contact_id: Mapped[str | None] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, default="bot")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = _uuid_col()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    direction: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[str] = mapped_column(String, default="text")
    body: Mapped[str | None] = mapped_column(Text)
    voice_transcript: Mapped[str | None] = mapped_column(Text)
    voice_audio_url: Mapped[str | None] = mapped_column(String)
    retrieval_score: Mapped[float | None] = mapped_column(Float)
    sources_cited: Mapped[list | None] = mapped_column(JSONB)
    external_message_id: Mapped[str | None] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class Case(Base):
    """Scheda diagnostica strutturata di una conversazione (Specifica_Definitiva_Tutor_AI,
    tabella 2). Un caso per conversazione: i campi vengono aggiornati via via che la
    diagnosi procede — vedi app/rag/case_extraction.py."""

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = _uuid_col()
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    area: Mapped[str | None] = mapped_column(Text)
    tecnica: Mapped[str | None] = mapped_column(Text)
    base_partenza: Mapped[str | None] = mapped_column(Text)
    capelli_bianchi: Mapped[str | None] = mapped_column(Text)
    storico_tecnico: Mapped[str | None] = mapped_column(Text)
    porosita: Mapped[str | None] = mapped_column(Text)
    servizio_eseguito: Mapped[str | None] = mapped_column(Text)
    formula_prodotti: Mapped[str | None] = mapped_column(Text)
    tempi_condizioni: Mapped[str | None] = mapped_column(Text)
    problema_osservato: Mapped[str | None] = mapped_column(Text)
    zona_coinvolta: Mapped[str | None] = mapped_column(Text)
    risultato_desiderato: Mapped[str | None] = mapped_column(Text)
    risultato_reale: Mapped[str | None] = mapped_column(Text)
    fonti_trovate: Mapped[list | None] = mapped_column(JSONB)
    livello_confidenza: Mapped[str | None] = mapped_column(Text)
    esito: Mapped[str | None] = mapped_column(Text)
    stato: Mapped[str] = mapped_column(String, default="RISPOSTA_AI")
    validated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    validated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Feedback(Base):
    """Feedback dell'utente su una risposta del tutor AI (Specifica_Definitiva_Tutor_AI,
    punto 11) — determina la transizione di stato del `Case` collegato."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = _uuid_col()
    case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"))
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"))
    tipo: Mapped[str] = mapped_column(String, nullable=False)
    nota: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Escalation(Base):
    __tablename__ = "escalations"

    id: Mapped[uuid.UUID] = _uuid_col()
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    reason: Mapped[str] = mapped_column(String, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    sources_consulted: Mapped[list | None] = mapped_column(JSONB)
    case_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String, default="open")
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = _uuid_col()
    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String, nullable=False)
    entity_type: Mapped[str | None] = mapped_column(String)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

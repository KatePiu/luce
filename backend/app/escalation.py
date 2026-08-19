"""Creazione delle escalation verso il tutor umano e sospensione dell'automazione."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Conversation, Escalation, Message
from app.notify import send_escalation_email
from app.rag.generate import CitedSource


def create_escalation(
    db: Session,
    conversation: Conversation,
    reason: str,
    summary: str,
    sources_consulted: list[CitedSource] | None = None,
) -> Escalation:
    escalation = Escalation(
        conversation_id=conversation.id,
        reason=reason,
        summary=summary,
        sources_consulted=[s.__dict__ for s in (sources_consulted or [])],
    )
    db.add(escalation)

    # L'automazione si ferma su questa conversazione finché un tutor umano non la richiude.
    conversation.status = "escalated"
    db.commit()
    db.refresh(escalation)

    _notify_human_tutor(db, conversation, escalation)
    return escalation


def _notify_human_tutor(db: Session, conversation: Conversation, escalation: Escalation) -> None:
    recent_messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(10)
        .all()
    )
    transcript = "\n".join(
        f"[{m.direction}] {m.body or m.voice_transcript or ''}" for m in reversed(recent_messages)
    )

    body = (
        f"Nuova escalation dal tutor AI LUCE.\n\n"
        f"Motivo: {escalation.reason}\n"
        f"Riepilogo: {escalation.summary}\n\n"
        f"Canale: {conversation.channel}\n"
        f"Conversazione: {conversation.id}\n\n"
        f"Ultimi messaggi:\n{transcript}\n"
    )
    send_escalation_email(subject=f"[LUCE] Escalation — {escalation.reason}", body=body)


def resolve_escalation(db: Session, escalation: Escalation, resolved_by, notes: str) -> Escalation:
    escalation.status = "resolved"
    escalation.resolution_notes = notes
    escalation.resolved_by = resolved_by
    from sqlalchemy import func

    escalation.resolved_at = func.now()
    db.commit()
    db.refresh(escalation)
    return escalation

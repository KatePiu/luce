"""Ricezione dei messaggi WhatsApp tramite webhook Superchat.

Schema payload verificato sulla documentazione ufficiale Superchat (19/08/2026):
{
  "event": "message_inbound",
  "id": "pe_...",                         <- id evento, usato per la deduplica
  "message": {
    "id": "...", "conversation_id": "...",
    "content": {"type": "text", "body": "..."}
                | {"type": "media", "file_id": "...", "mime_type": "..."}
  },
  "from": {"id": "...", "identifier": "+39..."},
  "to": {"channel_id": "mc_whatsapp_..."}
}
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal
from app.escalation import create_escalation
from app.integrations import superchat
from app.integrations.stt import transcribe_audio
from app.models import Conversation, Message
from app.rag.generate import answer_question

router = APIRouter(prefix="/webhooks", tags=["superchat"])


def _get_or_create_conversation(db: Session, external_conversation_id: str, contact_identifier: str) -> Conversation:
    conv = db.query(Conversation).filter(Conversation.external_conversation_id == external_conversation_id).one_or_none()
    if conv:
        return conv
    conv = Conversation(
        channel="whatsapp",
        external_conversation_id=external_conversation_id,
        external_contact_id=contact_identifier,
        status="bot",
    )
    db.add(conv)
    db.flush()
    return conv


def _extract_text(db: Session, content: dict) -> str:
    content_type = content.get("type")
    if content_type == "text":
        return content.get("body", "")
    if content_type == "media":
        file_id = content.get("file_id")
        if not file_id:
            raise ValueError("Messaggio media senza file_id")
        audio_bytes, mime_type = superchat.download_file_bytes(file_id)
        return transcribe_audio(audio_bytes, filename=f"{file_id}.ogg", mime_type=mime_type)
    raise ValueError(f"Tipo di contenuto non gestito: {content_type}")


@router.post("/superchat")
async def superchat_webhook(request: Request):
    raw_body = await request.body()
    if not superchat.verify_webhook_signature(raw_body, dict(request.headers)):
        raise HTTPException(status_code=401, detail="Firma webhook non valida")

    payload = await request.json()
    if payload.get("event") != "message_inbound":
        return {"status": "ignored"}  # rispondiamo solo ai messaggi in ingresso

    event_id = payload.get("id")
    message = payload.get("message", {})
    from_contact = payload.get("from", {})
    conversation_external_id = message.get("conversation_id")
    contact_identifier = from_contact.get("identifier")

    db = SessionLocal()
    try:
        conversation = _get_or_create_conversation(db, conversation_external_id, contact_identifier)

        try:
            text = _extract_text(db, message.get("content", {}))
        except ValueError:
            return {"status": "ignored", "reason": "unsupported_content_type"}

        inbound = Message(
            conversation_id=conversation.id,
            direction="inbound",
            kind="voice" if message.get("content", {}).get("type") == "media" else "text",
            body=text,
            external_message_id=event_id,
        )
        db.add(inbound)
        try:
            db.commit()
        except IntegrityError:
            # event_id già visto: webhook duplicato (Superchat può reinviare lo stesso evento).
            db.rollback()
            return {"status": "duplicate_ignored"}

        if conversation.status in ("escalated", "human_active"):
            # L'automazione resta ferma finché un tutor umano non richiude la conversazione.
            return {"status": "stored_no_reply", "reason": "human_active"}

        history = [
            {"role": "user" if m.direction == "inbound" else "assistant", "content": m.body or ""}
            for m in db.query(Message).filter(Message.conversation_id == conversation.id).order_by(Message.created_at.desc()).limit(12)
        ][::-1]

        result = answer_question(db, question=text, history=history)

        superchat.send_text_message(contact_identifier, result.text)

        db.add(
            Message(
                conversation_id=conversation.id,
                direction="outbound",
                kind="text",
                body=result.text,
                retrieval_score=result.retrieval_score,
                sources_cited=[s.__dict__ for s in result.cited_sources],
            )
        )
        db.commit()

        if result.escalate:
            create_escalation(db, conversation, result.escalation_reason or "insufficient_sources", summary=text)
            if settings.superchat_human_agent_user_id:
                superchat.assign_conversation_to_human(conversation_external_id, [settings.superchat_human_agent_user_id])

        return {"status": "ok"}
    finally:
        db.close()

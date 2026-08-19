from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.escalation import create_escalation
from app.integrations.stt import transcribe_audio
from app.models import Conversation, Message, User
from app.rag.generate import answer_question
from app.schemas import ChatMessageRequest, ChatMessageResponse, CitedSourceOut, ConversationSummary, MessageOut
from app.security import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])

HUMAN_TAKEOVER_NOTICE = (
    "Questa conversazione è stata presa in carico da un tutor umano: "
    "il tutor AI non risponde più qui finché non viene richiusa."
)


def _get_or_create_conversation(db: Session, user: User, conversation_id: str | None) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if not conv or conv.user_id != user.id:
            raise HTTPException(status_code=404, detail="Conversazione non trovata")
        return conv
    conv = Conversation(user_id=user.id, channel="web", status="bot")
    db.add(conv)
    db.flush()
    return conv


def _history_for_claude(db: Session, conversation: Conversation, limit: int = 12) -> list[dict]:
    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation.id)
        .order_by(Message.created_at.desc())
        .limit(limit)
        .all()
    )
    history = []
    for m in reversed(messages):
        role = "user" if m.direction == "inbound" else "assistant"
        history.append({"role": role, "content": m.body or m.voice_transcript or ""})
    return history


def _handle_incoming_text(db: Session, conversation: Conversation, text: str, kind: str, voice_transcript: str | None = None) -> ChatMessageResponse:
    history = _history_for_claude(db, conversation)

    db.add(
        Message(
            conversation_id=conversation.id,
            direction="inbound",
            kind=kind,
            body=text if kind == "text" else None,
            voice_transcript=voice_transcript,
        )
    )
    db.commit()

    if conversation.status in ("escalated", "human_active"):
        return ChatMessageResponse(conversation_id=str(conversation.id), text=HUMAN_TAKEOVER_NOTICE, escalated=True)

    result = answer_question(db, question=text, history=history)

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

    return ChatMessageResponse(
        conversation_id=str(conversation.id),
        text=result.text,
        escalated=result.escalate,
        cited_sources=[CitedSourceOut(**s.__dict__) for s in result.cited_sources],
        retrieval_score=result.retrieval_score,
    )


@router.post("/message", response_model=ChatMessageResponse)
def send_message(
    payload: ChatMessageRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ChatMessageResponse:
    conversation = _get_or_create_conversation(db, user, payload.conversation_id)
    return _handle_incoming_text(db, conversation, payload.text, kind="text")


@router.post("/voice", response_model=ChatMessageResponse)
async def send_voice_message(
    conversation_id: str | None = None,
    audio: UploadFile = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ChatMessageResponse:
    if audio is None:
        raise HTTPException(status_code=400, detail="File audio mancante")
    audio_bytes = await audio.read()
    transcript = transcribe_audio(audio_bytes, audio.filename or "voice.ogg", audio.content_type or "audio/ogg")

    conversation = _get_or_create_conversation(db, user, conversation_id)
    return _handle_incoming_text(db, conversation, transcript, kind="voice", voice_transcript=transcript)


@router.post("/conversations/{conversation_id}/escalate", response_model=ChatMessageResponse)
def request_human_tutor(
    conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ChatMessageResponse:
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")

    create_escalation(db, conversation, "user_requested", summary="L'utente ha chiesto di parlare con un tutor umano.")
    return ChatMessageResponse(
        conversation_id=str(conversation.id),
        text="Ho inoltrato la richiesta a un tutor umano. Verrai ricontattato appena possibile.",
        escalated=True,
    )


@router.get("/conversations", response_model=list[ConversationSummary])
def list_conversations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversations = (
        db.query(Conversation).filter(Conversation.user_id == user.id).order_by(Conversation.updated_at.desc()).all()
    )
    return [
        ConversationSummary(id=str(c.id), channel=c.channel, status=c.status, updated_at=c.updated_at)
        for c in conversations
    ]


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(conversation_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Conversazione non trovata")

    messages = (
        db.query(Message).filter(Message.conversation_id == conversation_id).order_by(Message.created_at).all()
    )
    return [
        MessageOut(
            id=str(m.id),
            direction=m.direction,
            kind=m.kind,
            body=m.body,
            voice_transcript=m.voice_transcript,
            sources_cited=m.sources_cited,
            created_at=m.created_at,
        )
        for m in messages
    ]

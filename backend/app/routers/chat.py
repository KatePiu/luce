from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.case_service import apply_feedback, case_to_diagnostic_dict, upsert_case_from_conversation
from app.db import get_db
from app.escalation import create_escalation
from app.integrations.stt import transcribe_audio
from app.models import Conversation, Message, User
from app.rag.generate import answer_question
from app.schemas import (
    FEEDBACK_TYPES,
    ChatMessageRequest,
    ChatMessageResponse,
    CitedSourceOut,
    ConversationSummary,
    FeedbackRequest,
    FeedbackResponse,
    MessageOut,
)
from app.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

HUMAN_TAKEOVER_NOTICE = (
    "Questa conversazione è stata presa in carico da un tutor umano: "
    "resto in pausa qui finché non viene richiusa, così non ricevi risposte doppie."
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
        return ChatMessageResponse(
            conversation_id=str(conversation.id), text=HUMAN_TAKEOVER_NOTICE, escalated=True, transcript=voice_transcript
        )

    result = answer_question(db, question=text, history=history)

    outbound_message = Message(
        conversation_id=conversation.id,
        direction="outbound",
        kind="text",
        body=result.text,
        retrieval_score=result.retrieval_score,
        sources_cited=[s.__dict__ for s in result.cited_sources],
    )
    db.add(outbound_message)
    db.commit()

    # Aggiorna la scheda diagnostica strutturata della conversazione (Specifica_Definitiva_
    # Tutor_AI, tabella 2) — best-effort: un fallimento qui non deve mai bloccare la risposta
    # già data all'utente.
    full_history = history + [{"role": "user", "content": text}, {"role": "assistant", "content": result.text}]
    case = upsert_case_from_conversation(
        db, conversation, full_history, result.escalate, result.cited_sources, result.retrieval_score
    )

    if result.escalate:
        # `result.text` è la risposta del tutor AI: quando arriva a un'escalation dopo aver
        # provato a chiarire la richiesta, contiene il report strutturato per il tutor (area,
        # prodotto/tecnica, fase, domanda precisa, contesto raccolto, informazione mancante) —
        # molto più utile del solo ultimo messaggio grezzo dell'utente. Allegata anche la
        # scheda diagnostica strutturata (tabella 3 del documento), come fotografia al
        # momento dell'escalation.
        create_escalation(
            db,
            conversation,
            result.escalation_reason or "insufficient_sources",
            summary=result.text,
            case_snapshot=case_to_diagnostic_dict(case),
        )

    return ChatMessageResponse(
        conversation_id=str(conversation.id),
        message_id=str(outbound_message.id),
        text=result.text,
        escalated=result.escalate,
        cited_sources=[CitedSourceOut(**s.__dict__) for s in result.cited_sources],
        retrieval_score=result.retrieval_score,
        transcript=voice_transcript,
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
    try:
        transcript = transcribe_audio(audio_bytes, audio.filename or "voice.ogg", audio.content_type or "audio/ogg")
    except Exception:
        logger.exception("Trascrizione del messaggio vocale fallita")
        raise HTTPException(
            status_code=503,
            detail="Il servizio di trascrizione vocale non è disponibile al momento. Riprova tra poco o scrivi la domanda in chat.",
        )

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
        text="Ho passato la richiesta a un tutor umano con il riepilogo della conversazione: ti ricontatterà appena possibile.",
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


@router.post("/messages/{message_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    message_id: str, payload: FeedbackRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> FeedbackResponse:
    if payload.tipo not in FEEDBACK_TYPES:
        raise HTTPException(status_code=422, detail=f"Tipo di feedback non valido: usare uno tra {FEEDBACK_TYPES}")

    message = db.get(Message, message_id)
    if not message:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")
    conversation = db.get(Conversation, message.conversation_id)
    if not conversation or conversation.user_id != user.id:
        raise HTTPException(status_code=404, detail="Messaggio non trovato")
    if message.direction != "outbound":
        raise HTTPException(status_code=400, detail="Il feedback si applica solo alle risposte del tutor AI")

    feedback, case = apply_feedback(db, message, payload.tipo, payload.nota)

    escalated = False
    if payload.tipo == "ho_dovuto_contattare_il_tutor" and conversation.status not in ("escalated", "human_active"):
        # Il feedback stesso dichiara che l'utente ha già dovuto contattare il tutor:
        # l'escalation va creata ora, non solo registrata come stato del caso.
        create_escalation(
            db,
            conversation,
            "user_requested",
            summary="L'utente ha segnalato via feedback di aver dovuto contattare il tutor.",
            case_snapshot=case_to_diagnostic_dict(case),
        )
        escalated = True

    return FeedbackResponse(
        id=str(feedback.id), tipo=feedback.tipo, case_stato=case.stato if case else None, escalated=escalated
    )

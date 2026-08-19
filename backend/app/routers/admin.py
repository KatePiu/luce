from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.db import get_db
from app.escalation import resolve_escalation
from app.models import Escalation, Source, Technique, User
from app.rag.generate import answer_question
from app.rag.ingest import SkippedJunkFile, ingest_file
from app.schemas import (
    ChatMessageResponse,
    CitedSourceOut,
    EscalationOut,
    ResolveEscalationRequest,
    SourceOut,
)
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sources/upload", response_model=SourceOut)
async def upload_source(
    file: UploadFile,
    technique_slug: str = Form(...),
    title: str | None = Form(None),
    video_title: str | None = Form(None),
    video_url: str | None = Form(None),
    document_url: str | None = Form(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SourceOut:
    raw_bytes = await file.read()
    try:
        source = ingest_file(
            db,
            filename=file.filename,
            raw_bytes=raw_bytes,
            technique_slug=technique_slug,
            title=title,
            video_title=video_title,
            video_url=video_url,
            document_url=document_url,
            uploaded_by=admin.id,
        )
    except SkippedJunkFile as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return _source_out(source)


def _source_out(source: Source) -> SourceOut:
    return SourceOut(
        id=str(source.id),
        title=source.title,
        technique=source.technique.slug if source.technique else None,
        origin_filename=source.origin_filename,
        origin_kind=source.origin_kind,
        version=source.version,
        status=source.status,
        video_url=source.video_url,
        document_url=source.document_url,
        updated_at=source.updated_at,
    )


@router.get("/sources", response_model=list[SourceOut])
def list_sources(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.updated_at.desc()).all()
    return [_source_out(s) for s in sources]


@router.patch("/sources/{source_id}/status", response_model=SourceOut)
def set_source_status(
    source_id: str, status: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    if status not in ("active", "disabled"):
        raise HTTPException(status_code=422, detail="Stato non valido: usare 'active' o 'disabled'")
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fonte non trovata")
    source.status = status
    db.commit()
    return _source_out(source)


@router.get("/escalations", response_model=list[EscalationOut])
def list_escalations(
    status: str | None = None, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    query = db.query(Escalation)
    if status:
        query = query.filter(Escalation.status == status)
    escalations = query.order_by(Escalation.created_at.desc()).all()
    return [
        EscalationOut(
            id=str(e.id),
            conversation_id=str(e.conversation_id),
            reason=e.reason,
            summary=e.summary,
            status=e.status,
            created_at=e.created_at,
        )
        for e in escalations
    ]


@router.post("/escalations/{escalation_id}/resolve", response_model=EscalationOut)
def resolve_escalation_endpoint(
    escalation_id: str,
    payload: ResolveEscalationRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    escalation = db.get(Escalation, escalation_id)
    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation non trovata")
    escalation = resolve_escalation(db, escalation, resolved_by=admin.id, notes=payload.notes)
    return EscalationOut(
        id=str(escalation.id),
        conversation_id=str(escalation.conversation_id),
        reason=escalation.reason,
        summary=escalation.summary,
        status=escalation.status,
        created_at=escalation.created_at,
    )


@router.post("/test-response", response_model=ChatMessageResponse)
def test_response(question: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Permette di testare una risposta del tutor prima di renderla operativa,
    senza creare una conversazione reale."""
    result = answer_question(db, question=question)
    return ChatMessageResponse(
        conversation_id="test",
        text=result.text,
        escalated=result.escalate,
        cited_sources=[CitedSourceOut(**s.__dict__) for s in result.cited_sources],
        retrieval_score=result.retrieval_score,
    )

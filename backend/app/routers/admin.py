from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Form, UploadFile
from sqlalchemy.orm import Session

from app.db import engine, get_db
from app.escalation import resolve_escalation
from app.models import Escalation, Source, Technique, User, Video
from app.schema_tools import apply_schema
from app.rag.generate import answer_question
from app.rag.ingest import SkippedJunkFile, ingest_file
from app.schemas import (
    ChatMessageResponse,
    CitedSourceOut,
    EscalationOut,
    ResolveEscalationRequest,
    SourceOut,
    VideoCreateRequest,
    VideoOut,
    VideoUpdateRequest,
)
from app.security import require_admin

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/sources/upload", response_model=SourceOut)
async def upload_source(
    file: UploadFile,
    technique_slug: str = Form(...),
    title: str | None = Form(None),
    video_id: str | None = Form(None),
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
            video_id=video_id,
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
        video_title=source.video.title if source.video else None,
        video_id=str(source.video_id) if source.video_id else None,
        document_url=source.document_url,
        updated_at=source.updated_at,
    )


def _video_out(video: Video) -> VideoOut:
    return VideoOut(
        id=str(video.id),
        title=video.title,
        platform=video.platform,
        url=video.url,
        technique=video.technique.slug if video.technique else None,
        description=video.description,
        updated_at=video.updated_at,
    )


@router.get("/videos", response_model=list[VideoOut])
def list_videos(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    videos = db.query(Video).order_by(Video.updated_at.desc()).all()
    return [_video_out(v) for v in videos]


@router.post("/videos", response_model=VideoOut)
def create_video(payload: VideoCreateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    technique = None
    if payload.technique_slug:
        technique = db.query(Technique).filter(Technique.slug == payload.technique_slug).one_or_none()
        if not technique:
            technique = Technique(slug=payload.technique_slug, label=payload.technique_slug.replace("_", " ").title())
            db.add(technique)
            db.flush()
    video = Video(
        title=payload.title,
        url=payload.url,
        platform=payload.platform,
        technique_id=technique.id if technique else None,
        description=payload.description,
    )
    db.add(video)
    db.commit()
    return _video_out(video)


@router.patch("/videos/{video_id}", response_model=VideoOut)
def update_video(
    video_id: str, payload: VideoUpdateRequest, admin: User = Depends(require_admin), db: Session = Depends(get_db)
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video non trovato")
    if payload.title is not None:
        video.title = payload.title
    if payload.url is not None:
        video.url = payload.url
    if payload.platform is not None:
        video.platform = payload.platform
    if payload.description is not None:
        video.description = payload.description
    if payload.technique_slug is not None:
        technique = db.query(Technique).filter(Technique.slug == payload.technique_slug).one_or_none()
        if not technique:
            technique = Technique(slug=payload.technique_slug, label=payload.technique_slug.replace("_", " ").title())
            db.add(technique)
            db.flush()
        video.technique_id = technique.id
    db.commit()
    return _video_out(video)


@router.delete("/videos/{video_id}", status_code=204)
def delete_video(video_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video non trovato")
    db.delete(video)
    db.commit()


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


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: str, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Elimina definitivamente una fonte e i suoi chunk indicizzati (cascade).
    Il file originale su Drive/disco non viene toccato: si può ricaricare in
    qualsiasi momento dal pannello."""
    source = db.get(Source, source_id)
    if not source:
        raise HTTPException(status_code=404, detail="Fonte non trovata")
    db.delete(source)
    db.commit()


@router.post("/system/apply-schema")
def apply_schema_endpoint(admin: User = Depends(require_admin)):
    """Applica backend/db/schema.sql al database — stesso effetto di
    'python -m scripts.init_db', richiamabile via API quando la Shell del
    servizio non è comoda da usare. Idempotente: sicuro da rieseguire."""
    try:
        count = apply_schema(engine)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")
    return {"status": "ok", "statements_applied": count}


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

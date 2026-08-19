"""Orchestrazione del flusso RAG: ricezione domanda -> recupero -> controllo soglia ->
generazione vincolata -> controlli anti-allucinazione -> risposta con fonti, o escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.integrations.anthropic_client import call_claude
from app.rag.groundedness import run_groundedness_checks
from app.rag.prompt import SYSTEM_PROMPT
from app.rag.retrieval import RetrievedChunk, detect_conflict, is_sufficient, retrieve

INSUFFICIENT_MATERIALS_MESSAGE = (
    "Nei materiali dell'Accademia non ho trovato informazioni sufficienti per "
    "rispondere con sicurezza a questo caso. Posso raccogliere i dettagli e "
    "inoltrare la richiesta a un tutor umano."
)

CONFLICT_MESSAGE = (
    "Ho trovato indicazioni non coerenti tra loro nei materiali dell'Accademia per questo caso. "
    "Per non darti un'indicazione sbagliata, preferisco non scegliere autonomamente: "
    "posso inoltrare la richiesta a un tutor umano, che verificherà quale fonte è corretta."
)


@dataclass
class CitedSource:
    source_id: str
    title: str
    video_title: str | None
    video_url: str | None
    document_url: str | None
    start_timestamp: str | None


@dataclass
class AnswerResult:
    text: str
    escalate: bool
    escalation_reason: str | None = None
    retrieval_score: float | None = None
    cited_sources: list[CitedSource] = field(default_factory=list)


def _build_context_block(chunks: list[RetrievedChunk]) -> str:
    parts = []
    for c in chunks:
        meta = f"[chunk_id={c.chunk_id} | fonte=\"{c.source_title}\""
        if c.video_title:
            meta += f" | video=\"{c.video_title}\""
        if c.start_timestamp:
            meta += f" | timestamp={c.start_timestamp}"
        meta += "]"
        parts.append(f"{meta}\n{c.text}")
    return "\n\n---\n\n".join(parts)


def _resolve_cited_sources(cited_ids: list[str], retrieved: list[RetrievedChunk]) -> list[CitedSource]:
    by_id = {c.chunk_id: c for c in retrieved}
    seen_sources: set[str] = set()
    out: list[CitedSource] = []
    for cid in cited_ids:
        chunk = by_id.get(cid)
        if not chunk or chunk.source_id in seen_sources:
            continue
        seen_sources.add(chunk.source_id)
        out.append(
            CitedSource(
                source_id=chunk.source_id,
                title=chunk.source_title,
                video_title=chunk.video_title,
                video_url=chunk.video_url,
                document_url=chunk.document_url,
                start_timestamp=chunk.start_timestamp,
            )
        )
    return out


def answer_question(
    db: Session,
    question: str,
    history: list[dict] | None = None,
    technique_hint: str | None = None,
) -> AnswerResult:
    retrieved = retrieve(db, question, technique_slug=technique_hint)

    if not is_sufficient(retrieved):
        return AnswerResult(
            text=INSUFFICIENT_MATERIALS_MESSAGE,
            escalate=True,
            escalation_reason="no_sources" if not retrieved else "insufficient_sources",
            retrieval_score=retrieved[0].score if retrieved else None,
        )

    if detect_conflict(retrieved):
        return AnswerResult(
            text=CONFLICT_MESSAGE,
            escalate=True,
            escalation_reason="conflicting_sources",
            retrieval_score=retrieved[0].score,
            cited_sources=_resolve_cited_sources([retrieved[0].chunk_id, retrieved[1].chunk_id], retrieved),
        )

    context_block = _build_context_block(retrieved)
    user_message = f"CONTESTO RECUPERATO DAI MATERIALI DELL'ACCADEMIA:\n\n{context_block}\n\nDOMANDA DEL PARRUCCHIERE:\n{question}"

    raw_response = call_claude(system=SYSTEM_PROMPT, user_message=user_message, history=history)

    result = run_groundedness_checks(raw_response, retrieved)
    if not result.passed:
        return AnswerResult(
            text=INSUFFICIENT_MATERIALS_MESSAGE,
            escalate=True,
            escalation_reason="insufficient_sources",
            retrieval_score=retrieved[0].score,
        )

    cited_sources = _resolve_cited_sources(result.cited_chunk_ids or [], retrieved)
    return AnswerResult(
        text=result.visible_text,
        escalate=False,
        retrieval_score=retrieved[0].score,
        cited_sources=cited_sources,
    )

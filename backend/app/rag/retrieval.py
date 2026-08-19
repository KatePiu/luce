"""Recupero dei passaggi più pertinenti dalla base documentale (RAG - fase di retrieval)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Source, Technique
from app.rag.embeddings import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_id: str
    source_title: str
    video_title: str | None
    video_url: str | None
    document_url: str | None
    start_timestamp: str | None
    end_timestamp: str | None
    text: str
    score: float  # similarità coseno, 0-1 (1 = identico)


def retrieve(db: Session, query: str, technique_slug: str | None = None, top_k: int | None = None) -> list[RetrievedChunk]:
    """Ricerca semantica sui chunk attivi, opzionalmente filtrata per tecnica/categoria.

    Il punteggio restituito è la similarità coseno: pgvector espone l'operatore
    `<=>` come *distanza* coseno (0 = identico, 2 = opposto), quindi la
    similarità è `1 - distanza`.
    """
    top_k = top_k or settings.retrieval_top_k
    query_embedding = embed_query(query)

    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(Chunk, Source, distance.label("distance"))
        .join(Source, Chunk.source_id == Source.id)
        .where(Source.status == "active")
    )

    if technique_slug:
        stmt = stmt.join(Technique, Source.technique_id == Technique.id).where(Technique.slug == technique_slug)

    stmt = stmt.order_by(distance).limit(top_k)

    results = []
    for chunk, source, dist in db.execute(stmt).all():
        score = max(0.0, 1.0 - float(dist))
        results.append(
            RetrievedChunk(
                chunk_id=str(chunk.id),
                source_id=str(source.id),
                source_title=source.title,
                video_title=source.video_title,
                video_url=source.video_url,
                document_url=source.document_url,
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
                text=chunk.text,
                score=score,
            )
        )
    return results


def is_sufficient(chunks: list[RetrievedChunk]) -> bool:
    """Soglia minima di affidabilità: se il miglior risultato è sotto soglia, i materiali
    non sono considerati sufficienti per generare una risposta tecnica (vedi app/rag/generate.py)."""
    if not chunks:
        return False
    return chunks[0].score >= settings.retrieval_min_score


def detect_conflict(chunks: list[RetrievedChunk]) -> bool:
    """Euristica minima per i conflitti tra fonti: se i chunk migliori provengono da fonti
    diverse con priority diverse e punteggi molto vicini, segnaliamo un possibile conflitto
    da lasciar decidere al controllo di groundedness / a un tutor umano, invece di scegliere
    automaticamente quale fonte privilegiare."""
    if len(chunks) < 2:
        return False
    top = chunks[0]
    close_but_different_source = [
        c for c in chunks[1:3] if c.source_id != top.source_id and (top.score - c.score) < 0.03
    ]
    return len(close_but_different_source) > 0

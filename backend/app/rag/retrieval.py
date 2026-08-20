"""Recupero dei passaggi più pertinenti dalla base documentale (RAG - fase di retrieval)."""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Source, Technique, Video
from app.rag.embeddings import embed_query

CASI_PARTICOLARI_SLUG = "casi_particolari"


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_id: str
    source_title: str
    video_title: str | None
    video_url: str | None
    video_platform: str | None
    document_url: str | None
    start_timestamp: str | None
    end_timestamp: str | None
    text: str
    score: float  # similarità coseno, 0-1 (1 = identico)


@dataclass
class VideoCandidate:
    """Un video indicizzato solo per titolo (nessuna trascrizione disponibile,
    o comunque non tra i passaggi recuperati) ma potenzialmente pertinente —
    vedi punti 2 e 19 del brief: va comunque proposto come link, senza
    descriverne il contenuto (non c'è testo su cui basare quella descrizione)."""

    video_id: str
    title: str
    url: str
    platform: str


def _base_query():
    return (
        select(Chunk, Source, Video)
        .join(Source, Chunk.source_id == Source.id)
        .outerjoin(Video, Source.video_id == Video.id)
        .where(Source.status == "active")
    )


def _rows_to_chunks(rows, distances) -> list[RetrievedChunk]:
    results = []
    for (chunk, source, video), dist in zip(rows, distances):
        score = max(0.0, 1.0 - float(dist))
        results.append(
            RetrievedChunk(
                chunk_id=str(chunk.id),
                source_id=str(source.id),
                source_title=source.title,
                video_title=video.title if video else None,
                video_url=video.url if video else None,
                video_platform=video.platform if video else None,
                document_url=source.document_url,
                start_timestamp=chunk.start_timestamp,
                end_timestamp=chunk.end_timestamp,
                text=chunk.text,
                score=score,
            )
        )
    return results


def retrieve(db: Session, query: str, technique_slug: str | None = None, top_k: int | None = None) -> list[RetrievedChunk]:
    """Ricerca semantica sui chunk attivi, opzionalmente filtrata per tecnica/categoria.

    Il punteggio restituito è la similarità coseno: pgvector espone l'operatore
    `<=>` come *distanza* coseno (0 = identico, 2 = opposto), quindi la
    similarità è `1 - distanza`.
    """
    top_k = top_k or settings.retrieval_top_k
    query_embedding = embed_query(query)

    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = _base_query()

    if technique_slug:
        stmt = stmt.join(Technique, Source.technique_id == Technique.id).where(Technique.slug == technique_slug)

    stmt = stmt.add_columns(distance.label("distance")).order_by(distance).limit(top_k)

    rows = db.execute(stmt).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    distances = [r[3] for r in rows]
    return _rows_to_chunks(triples, distances)


def retrieve_with_priority(
    db: Session, query: str, top_k: int | None = None
) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
    """Due corsie di recupero, come richiesto per i problemi di colorazione (brief,
    punti 12-16 e 21): i "casi particolari" vengono cercati per primi e a parte,
    così il prompt può dar loro priorità quando pertinenti, senza escludere le
    fonti generali (guide, prodotti) che restano comunque disponibili come
    contesto complementare per la procedura/i prodotti da usare.

    Ritorna (chunk_prioritari_da_casi_particolari, chunk_generali_dalle_altre_fonti).
    """
    priority = retrieve(db, query, technique_slug=CASI_PARTICOLARI_SLUG, top_k=top_k)

    top_k = top_k or settings.retrieval_top_k
    query_embedding = embed_query(query)
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        _base_query()
        .join(Technique, Source.technique_id == Technique.id)
        .where(Technique.slug != CASI_PARTICOLARI_SLUG)
        .add_columns(distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    distances = [r[3] for r in rows]
    general = _rows_to_chunks(triples, distances)

    return priority, general


_STOPWORDS = {
    "il", "lo", "la", "i", "gli", "le", "un", "una", "di", "a", "da", "in", "con", "su", "per", "tra", "fra",
    "e", "o", "che", "come", "cosa", "quale", "quali", "dove", "quando", "del", "della", "dei", "delle",
    "al", "allo", "alla", "ai", "agli", "alle", "si", "mi", "ti", "ci", "vi", "non", "è", "sono", "ho", "hai",
}


def _keywords(text: str) -> set[str]:
    words = re.findall(r"[a-zàèéìòù]+", text.lower())
    return {w for w in words if len(w) > 2 and w not in _STOPWORDS}


def find_candidate_videos(db: Session, query: str, limit: int = 3) -> list[VideoCandidate]:
    """Cerca video il cui titolo (o descrizione) condivide parole chiave con la
    domanda — usato per proporre video senza trascrizione (punti 2, 19): non è
    una ricerca semantica sul contenuto (che non esiste), solo un confronto
    testuale sul titolo, abbastanza per capire se un video sembra pertinente."""
    query_words = _keywords(query)
    if not query_words:
        return []

    videos = db.query(Video).all()
    scored: list[tuple[int, Video]] = []
    for video in videos:
        title_words = _keywords(video.title) | _keywords(video.description or "")
        overlap = len(query_words & title_words)
        if overlap > 0:
            scored.append((overlap, video))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [
        VideoCandidate(video_id=str(v.id), title=v.title, url=v.url, platform=v.platform)
        for _, v in scored[:limit]
    ]


def is_sufficient(chunks: list[RetrievedChunk]) -> bool:
    """Soglia minima di affidabilità: se il miglior risultato è sotto soglia, i materiali
    non sono considerati sufficienti per generare una risposta tecnica (vedi app/rag/generate.py)."""
    if not chunks:
        return False
    return chunks[0].score >= settings.retrieval_min_score


def detect_conflict(chunks: list[RetrievedChunk]) -> RetrievedChunk | None:
    """Euristica minima per i conflitti tra fonti: se il chunk migliore e un altro chunk da
    una fonte diversa hanno punteggi molto vicini, segnaliamo un possibile conflitto da
    lasciar decidere al controllo di groundedness / a un tutor umano, invece di scegliere
    automaticamente quale fonte privilegiare. Restituisce il chunk in conflitto (per citarlo
    correttamente), o None se non c'è conflitto.

    Entrambi i chunk devono superare individualmente la soglia minima di affidabilità: se il
    punteggio migliore è già al limite della soglia, un secondo risultato mediocre e solo
    vagamente pertinente (rumore di fondo, non un'informazione realmente in disaccordo)
    finirebbe altrimenti per essere interpretato come una fonte "in conflitto", bloccando
    inutilmente domande su procedure già ben coperte da un'unica guida pertinente.
    """
    if len(chunks) < 2:
        return None
    top = chunks[0]
    if top.score < settings.retrieval_min_score:
        return None
    for c in chunks[1:3]:
        if c.source_id != top.source_id and c.score >= settings.retrieval_min_score and (top.score - c.score) < 0.03:
            return c
    return None

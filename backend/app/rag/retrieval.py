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

# Le trascrizioni video (CSV) non vanno mai usate come fonte di contenuto per
# rispondere: solo le "ricostruzioni discorsive" (guide .docx, tabelle .txt) sono
# fonte di verità per il merito della risposta. Il CSV serve esclusivamente a
# individuare il timestamp del video sullo stesso argomento — vedi
# `_attach_video_timestamps`. Richiesta esplicita dell'Accademia dopo un caso reale
# in cui una trascrizione veniva citata come se fosse una fonte alternativa di fatti.
TRANSCRIPT_ORIGIN_KIND = "transcript_csv"


@dataclass
class RetrievedChunk:
    chunk_id: str
    source_id: str
    source_title: str
    video_id: str | None
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
                video_id=str(source.video_id) if source.video_id else None,
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


def retrieve(
    db: Session,
    query: str,
    technique_slug: str | None = None,
    top_k: int | None = None,
    query_embedding: list[float] | None = None,
    exclude_transcripts: bool = False,
) -> list[RetrievedChunk]:
    """Ricerca semantica sui chunk attivi, opzionalmente filtrata per tecnica/categoria.

    Il punteggio restituito è la similarità coseno: pgvector espone l'operatore
    `<=>` come *distanza* coseno (0 = identico, 2 = opposto), quindi la
    similarità è `1 - distanza`.

    `exclude_transcripts` esclude le fonti CSV (trascrizioni): usarlo per la ricerca
    di CONTENUTO, dato che solo le guide scritte devono rispondere nel merito — vedi
    `TRANSCRIPT_ORIGIN_KIND`. `query_embedding` evita di ricalcolare l'embedding
    quando già disponibile (ogni chiamata all'API di embedding ha un costo).
    """
    top_k = top_k or settings.retrieval_top_k
    query_embedding = query_embedding or embed_query(query)

    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = _base_query()

    if technique_slug:
        stmt = stmt.join(Technique, Source.technique_id == Technique.id).where(Technique.slug == technique_slug)
    if exclude_transcripts:
        stmt = stmt.where(Source.origin_kind != TRANSCRIPT_ORIGIN_KIND)

    stmt = stmt.add_columns(distance.label("distance")).order_by(distance).limit(top_k)

    rows = db.execute(stmt).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    distances = [r[3] for r in rows]
    return _rows_to_chunks(triples, distances)


def _attach_video_timestamps(db: Session, chunks: list[RetrievedChunk], query_embedding: list[float]) -> list[RetrievedChunk]:
    """Le fonti di contenuto (guide .docx, tabelle .txt) non hanno un timestamp proprio.
    Per ognuna, se collegata a un video che ha anche una trascrizione CSV indicizzata,
    cerca il passaggio della trascrizione più pertinente alla domanda e ne usa il
    timestamp di inizio — SENZA usare il testo della trascrizione come contenuto: serve
    solo a individuare il minuto del video in cui si parla di quell'argomento."""
    distance = Chunk.embedding.cosine_distance(query_embedding)
    for c in chunks:
        if c.start_timestamp or not c.video_id:
            continue
        stmt = (
            _base_query()
            .where(Source.origin_kind == TRANSCRIPT_ORIGIN_KIND, Source.video_id == c.video_id)
            .add_columns(distance.label("distance"))
            .order_by(distance)
            .limit(1)
        )
        row = db.execute(stmt).first()
        if row:
            c.start_timestamp = row[0].start_timestamp
            c.end_timestamp = row[0].end_timestamp
    return chunks


def retrieve_with_priority(
    db: Session, query: str, top_k: int | None = None
) -> tuple[list[RetrievedChunk], list[RetrievedChunk]]:
    """Due corsie di recupero, come richiesto per i problemi di colorazione (brief,
    punti 12-16 e 21): i "casi particolari" vengono cercati per primi e a parte,
    così il prompt può dar loro priorità quando pertinenti, senza escludere le
    fonti generali (guide, prodotti) che restano comunque disponibili come
    contesto complementare per la procedura/i prodotti da usare.

    Entrambe le corsie cercano solo tra le fonti di contenuto (guide scritte,
    tabelle): le trascrizioni CSV vengono escluse dalla ricerca semantica e
    consultate solo dopo, per attaccare un timestamp video pertinente — vedi
    `_attach_video_timestamps`.

    Ritorna (chunk_prioritari_da_casi_particolari, chunk_generali_dalle_altre_fonti).
    """
    query_embedding = embed_query(query)
    priority = retrieve(
        db, query, technique_slug=CASI_PARTICOLARI_SLUG, top_k=top_k, query_embedding=query_embedding, exclude_transcripts=True
    )

    top_k = top_k or settings.retrieval_top_k
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = (
        _base_query()
        .join(Technique, Source.technique_id == Technique.id)
        .where(Technique.slug != CASI_PARTICOLARI_SLUG, Source.origin_kind != TRANSCRIPT_ORIGIN_KIND)
        .add_columns(distance.label("distance"))
        .order_by(distance)
        .limit(top_k)
    )
    rows = db.execute(stmt).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    distances = [r[3] for r in rows]
    general = _rows_to_chunks(triples, distances)
    general = _boost_named_technique(db, query, general, query_embedding)

    priority = _attach_video_timestamps(db, priority, query_embedding)
    general = _attach_video_timestamps(db, general, query_embedding)

    return priority, general


_TECHNIQUE_NUMBER_RE = re.compile(r"tecnica[^\d]{0,20}?(\d+)", re.IGNORECASE)


def _extract_technique_number(text: str) -> str | None:
    match = _TECHNIQUE_NUMBER_RE.search(text)
    return match.group(1) if match else None


def _boost_named_technique(db: Session, query: str, chunks: list[RetrievedChunk], query_embedding: list[float]) -> list[RetrievedChunk]:
    """Se la domanda cita un numero di tecnica preciso (es. "tecnica n°2"), le guide
    della stessa serie (es. Infusion 1/2/3/4) usano un linguaggio molto simile tra loro
    e la sola similarità semantica può confondere una tecnica con un'altra vicina —
    trovato durante il test end-to-end del punto 25 (una domanda su "Infusion Tecnica 2"
    non recuperava con punteggio sufficiente la guida corretta).

    Qui si esclude dai risultati qualunque fonte che citi ESPLICITAMENTE un numero
    diverso nello stesso formato (fuorviante, tecnica sbagliata), e si aggiungono i
    chunk più pertinenti delle fonti (di contenuto, non trascrizioni) che citano il
    numero richiesto, anche se la sola ricerca vettoriale non li avesse messi tra i
    risultati migliori.
    """
    number = _extract_technique_number(query)
    if not number:
        return chunks

    filtered = [c for c in chunks if (_extract_technique_number(c.source_title) or number) == number]

    matching_source_ids = [
        s.id
        for s in db.query(Source).filter(Source.status == "active", Source.origin_kind != TRANSCRIPT_ORIGIN_KIND).all()
        if _extract_technique_number(s.title) == number
    ]
    if not matching_source_ids:
        return filtered

    present_ids = {c.chunk_id for c in filtered}
    distance = Chunk.embedding.cosine_distance(query_embedding)
    stmt = _base_query().where(Source.id.in_(matching_source_ids)).add_columns(distance.label("distance")).order_by(distance).limit(3)
    rows = db.execute(stmt).all()
    triples = [(r[0], r[1], r[2]) for r in rows]
    distances = [r[3] for r in rows]
    for extra in _rows_to_chunks(triples, distances):
        if extra.chunk_id not in present_ids:
            filtered.append(extra)

    filtered.sort(key=lambda c: c.score, reverse=True)
    return filtered


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


def sort_by_relevance_then_richness(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Ordina per rilevanza (punteggio, arrotondato) e poi per ricchezza di contenuto
    (numero di parole chiave nel testo del chunk).

    A parità di rilevanza — stesso punteggio arrotondato a due decimali, cioè
    entro il margine già usato da `detect_conflict` per considerare due fonti
    "vicine" — tra due fonti che trattano lo stesso argomento con pertinenza
    praticamente identica si preferisce quella più completa/dettagliata, invece
    di lasciare l'ordine al caso (es. l'ordine di inserimento nel database).
    """
    return sorted(chunks, key=lambda c: (round(c.score, 2), len(_keywords(c.text))), reverse=True)


def is_sufficient(chunks: list[RetrievedChunk]) -> bool:
    """Soglia minima di affidabilità: se il miglior risultato è sotto soglia, i materiali
    non sono considerati sufficienti per generare una risposta tecnica (vedi app/rag/generate.py)."""
    if not chunks:
        return False
    return chunks[0].score >= settings.retrieval_min_score


def _chunks_agree(text_a: str, text_b: str) -> bool:
    """Due chunk che condividono gran parte delle parole chiave dicono verosimilmente la
    stessa cosa: non è un conflitto reale, solo la stessa informazione presente in più
    fonti (es. una guida caricata due volte per errore con un nome file leggermente
    diverso, o una guida scritta e la trascrizione dello stesso passaggio del video)."""
    words_a, words_b = _keywords(text_a), _keywords(text_b)
    if not words_a or not words_b:
        return False
    overlap = len(words_a & words_b) / min(len(words_a), len(words_b))
    return overlap >= 0.6


def detect_conflict(chunks: list[RetrievedChunk]) -> RetrievedChunk | None:
    """Euristica minima per i conflitti tra fonti: se il chunk migliore e un altro chunk da
    una fonte diversa hanno punteggi molto vicini E dicono cose diverse, segnaliamo un
    possibile conflitto da lasciar decidere al controllo di groundedness / a un tutor
    umano, invece di scegliere automaticamente quale fonte privilegiare. Restituisce il
    chunk in conflitto (per citarlo correttamente), o None se non c'è conflitto.

    Entrambi i chunk devono superare individualmente la soglia minima di affidabilità: se il
    punteggio migliore è già al limite della soglia, un secondo risultato mediocre e solo
    vagamente pertinente (rumore di fondo, non un'informazione realmente in disaccordo)
    finirebbe altrimenti per essere interpretato come una fonte "in conflitto", bloccando
    inutilmente domande su procedure già ben coperte da un'unica guida pertinente.

    Bug reale trovato in produzione: un file guida caricato due volte con un nome quasi
    identico (stesso contenuto, "_md.docx" vs ".md.docx") veniva segnalato come fonte "in
    conflitto" con se stesso, perché la verifica guardava solo la vicinanza dei punteggi
    tra fonti diverse, mai se il contenuto fosse davvero discordante — bloccando una
    domanda a cui i materiali sapevano rispondere correttamente e senza ambiguità.
    """
    if len(chunks) < 2:
        return None
    top = chunks[0]
    if top.score < settings.retrieval_min_score:
        return None
    for c in chunks[1:3]:
        if c.source_id == top.source_id:
            continue
        if c.score < settings.retrieval_min_score or (top.score - c.score) >= 0.03:
            continue
        if _chunks_agree(top.text, c.text):
            continue
        return c
    return None

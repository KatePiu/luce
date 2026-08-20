"""Ingestione di un file caricato dal pannello admin: parsing -> chunking -> embedding -> DB.

Aggiornare una fonte esistente reindicizza solo i suoi chunk (cancella i vecchi,
crea i nuovi), non l'intero indice — come richiesto dal brief.
"""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from app.config import settings
from app.models import Chunk, Source, Technique
from app.rag.chunking import is_junk_filename, parse_case_table, parse_docx, parse_generic_csv_table, parse_transcript_csv
from app.rag.embeddings import embed_texts


class SkippedJunkFile(Exception):
    pass


def _guess_origin_kind(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".csv"):
        return "transcript_csv"
    # La tabella "casi particolari" è testo semplice con righe "Caso NNN | ...":
    # solo un .txt con "caso/casi" nel nome va analizzato con quel parser. Un
    # .docx con lo stesso nome è un documento Word vero e proprio (guida) — va
    # controllato PRIMA di guardare "caso/casi" nel nome, altrimenti un file
    # come "Casi_particolari_md.docx" verrebbe letto come se fosse testo
    # semplice, producendo zero contenuto valido.
    if lower.endswith((".docx", ".md")):
        return "guide_doc"
    if lower.endswith(".txt") and ("caso" in lower or "casi" in lower):
        return "case_table"
    if "scheda_prodotto" in lower or "prodotti" in lower:
        return "product_sheet"
    return "other"


def _get_or_create_technique(db: Session, slug: str, label: str | None = None) -> Technique:
    technique = db.query(Technique).filter(Technique.slug == slug).one_or_none()
    if technique:
        return technique
    technique = Technique(slug=slug, label=label or slug.replace("_", " ").title())
    db.add(technique)
    db.flush()
    return technique


def ingest_file(
    db: Session,
    filename: str,
    raw_bytes: bytes,
    technique_slug: str,
    title: str | None = None,
    video_id: str | None = None,
    document_url: str | None = None,
    uploaded_by=None,
) -> Source:
    if is_junk_filename(filename):
        raise SkippedJunkFile(f"'{filename}' è un file di metadati macOS (prefisso '._'): escluso dall'ingestione.")

    origin_kind = _guess_origin_kind(filename)
    checksum = hashlib.sha256(raw_bytes).hexdigest()

    if origin_kind == "transcript_csv":
        drafts = parse_transcript_csv(raw_bytes, settings.chunk_target_chars, settings.chunk_overlap_chars)
        if not drafts:
            # Non ha le colonne di una trascrizione (Speaker Name/Start Time/End
            # Time/Text): probabilmente è una tabella generica (es. elenco
            # prodotti) esportata in CSV invece che come scheda Word.
            drafts = parse_generic_csv_table(raw_bytes)
            if drafts:
                origin_kind = "product_sheet"
    elif origin_kind == "case_table":
        drafts = parse_case_table(raw_bytes)
    elif origin_kind in ("guide_doc", "product_sheet"):
        drafts = parse_docx(raw_bytes, settings.chunk_target_chars, settings.chunk_overlap_chars)
    else:
        raise ValueError(f"Formato non supportato per '{filename}': attesi .csv, .docx o tabella casi (.txt)")

    if not drafts:
        raise ValueError(f"Nessun contenuto estratto da '{filename}' — file vuoto o formato inatteso.")

    technique = _get_or_create_technique(db, technique_slug)

    existing = (
        db.query(Source)
        .filter(Source.origin_filename == filename, Source.technique_id == technique.id)
        .one_or_none()
    )

    if existing:
        if existing.checksum == checksum:
            return existing  # contenuto invariato, nessuna reindicizzazione necessaria
        db.query(Chunk).filter(Chunk.source_id == existing.id).delete()
        source = existing
        source.version += 1
        source.checksum = checksum
    else:
        source = Source(
            title=title or filename,
            technique_id=technique.id,
            origin_filename=filename,
            origin_kind=origin_kind,
            checksum=checksum,
            uploaded_by=uploaded_by,
        )
        db.add(source)

    source.video_id = video_id or source.video_id
    source.document_url = document_url or source.document_url
    db.flush()

    embeddings = embed_texts([d.text for d in drafts])
    for seq, (draft, embedding) in enumerate(zip(drafts, embeddings)):
        db.add(
            Chunk(
                source_id=source.id,
                seq=seq,
                text=draft.text,
                start_timestamp=draft.start_timestamp,
                end_timestamp=draft.end_timestamp,
                embedding=embedding,
            )
        )

    db.commit()
    return source

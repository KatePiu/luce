"""Estrazione e suddivisione in chunk dei materiali dell'Accademia.

Supporta i formati reali trovati in _TRASCRIZIONI:
- CSV di trascrizione, in due varianti di delimitatore/colonne (vedi `parse_transcript_csv`)
- CSV tabellare generico (es. elenco prodotti), quando non è una trascrizione (`parse_generic_csv_table`)
- Documenti guida (.docx) — testo discorsivo, senza timestamp
- Tabella casi particolari (.txt, righe "Caso NNN | campo | campo | ...")

Ogni funzione restituisce una lista di `ChunkDraft`, pronta per l'embedding.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field


@dataclass
class ChunkDraft:
    text: str
    start_timestamp: str | None = None
    end_timestamp: str | None = None


# I file macOS "._nomefile" sono metadati AppleDouble, non contenuto reale.
JUNK_FILENAME_RE = re.compile(r"^\._")


def is_junk_filename(filename: str) -> bool:
    return bool(JUNK_FILENAME_RE.match(filename))


def _normalize_timestamp(raw: str) -> str:
    """Le trascrizioni usano HH:MM:SS:FF (con fotogrammi). Normalizza a HH:MM:SS per citarlo all'utente."""
    parts = raw.strip().split(":")
    if len(parts) >= 3:
        return ":".join(parts[:3])
    return raw.strip()


def parse_transcript_csv(raw_bytes: bytes, target_chars: int, overlap_chars: int) -> list[ChunkDraft]:
    """Analizza un CSV di trascrizione.

    Varianti osservate nei materiali reali:
      1) delimitatore ',', colonne: "Speaker Name","Start Time","End Time","Text"
      2) delimitatore ';', colonne: Speaker Name;Start Time;End Time;Text;Testo completo
         (la quinta colonna duplica il testo della quarta — viene ignorata)
    """
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return []

    field_map = {f.strip().lower(): f for f in reader.fieldnames}

    def col(row: dict, *names: str) -> str:
        for name in names:
            key = field_map.get(name)
            if key and row.get(key):
                return row[key].strip()
        return ""

    rows = []
    for row in reader:
        raw_text = col(row, "text")
        if not raw_text:
            continue
        rows.append(
            {
                "start": _normalize_timestamp(col(row, "start time")),
                "end": _normalize_timestamp(col(row, "end time")),
                "text": raw_text,
            }
        )

    return _group_rows_into_chunks(rows, target_chars, overlap_chars)


def parse_generic_csv_table(raw_bytes: bytes) -> list[ChunkDraft]:
    """CSV tabellare generico (es. elenco prodotti con colonne libere come
    "Linea;Prodotto;A cosa serve"), diverso dal formato di trascrizione: non ha
    colonne Speaker/Start Time/End Time. Usato come fallback quando un .csv non
    è una trascrizione — vedi ingest.py. Una riga = un chunk, con le coppie
    intestazione/valore unite in una frase leggibile."""
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
        dialect.delimiter = ";" if sample.count(";") > sample.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    if not reader.fieldnames:
        return []
    headers = [h.strip() for h in reader.fieldnames if h and h.strip()]

    chunks: list[ChunkDraft] = []
    for row in reader:
        parts = [f"{h}: {v.strip()}" for h in headers if (v := row.get(h)) and v.strip()]
        if parts:
            chunks.append(ChunkDraft(text=". ".join(parts)))
    return chunks


def _group_rows_into_chunks(rows: list[dict], target_chars: int, overlap_chars: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    buf: list[dict] = []
    buf_len = 0

    def flush():
        if not buf:
            return
        text = " ".join(r["text"] for r in buf)
        chunks.append(
            ChunkDraft(text=text, start_timestamp=buf[0]["start"] or None, end_timestamp=buf[-1]["end"] or None)
        )

    for row in rows:
        row_len = len(row["text"]) + 1
        if buf and buf_len + row_len > target_chars:
            flush()
            # overlap: mantieni le ultime righe finché non si supera overlap_chars
            carry: list[dict] = []
            carry_len = 0
            for r in reversed(buf):
                if carry_len >= overlap_chars:
                    break
                carry.insert(0, r)
                carry_len += len(r["text"]) + 1
            buf = carry
            buf_len = carry_len
        buf.append(row)
        buf_len += row_len

    flush()
    return chunks


def parse_docx(raw_bytes: bytes, target_chars: int, overlap_chars: int) -> list[ChunkDraft]:
    """Estrae il testo di un documento guida .docx e lo suddivide in chunk (nessun timestamp: sono guide discorsive)."""
    from docx import Document  # import locale: pesante, serve solo qui

    doc = Document(io.BytesIO(raw_bytes))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return _group_text_blocks(paragraphs, target_chars, overlap_chars)


def _group_text_blocks(blocks: list[str], target_chars: int, overlap_chars: int) -> list[ChunkDraft]:
    chunks: list[ChunkDraft] = []
    buf: list[str] = []
    buf_len = 0

    def flush():
        if buf:
            chunks.append(ChunkDraft(text="\n".join(buf)))

    for block in blocks:
        block_len = len(block) + 1
        if buf and buf_len + block_len > target_chars:
            flush()
            carry: list[str] = []
            carry_len = 0
            for b in reversed(buf):
                if carry_len >= overlap_chars:
                    break
                carry.insert(0, b)
                carry_len += len(b) + 1
            buf = carry
            buf_len = carry_len
        buf.append(block)
        buf_len += block_len

    flush()
    return chunks


CASE_LINE_RE = re.compile(r"^Caso\s+\d+\s*\|")


def parse_case_table(raw_bytes: bytes) -> list[ChunkDraft]:
    """Tabella 'casi particolari': una riga = un caso = un chunk atomico.

    Ogni riga è già una singola unità di informazione autosufficiente (base naturale,
    colore attuale, situazione, base di partenza desiderata, intervento) — non va
    ulteriormente frammentata né unita ad altre righe.
    """
    text = raw_bytes.decode("utf-8-sig", errors="replace")
    lines = [l.strip() for l in text.splitlines() if l.strip()]

    header_lines = [l for l in lines if not CASE_LINE_RE.match(l)]
    header = "\n".join(header_lines)

    chunks: list[ChunkDraft] = []
    for line in lines:
        if CASE_LINE_RE.match(line):
            # Il formato/nota vengono anteposti per dare contesto al chunk isolato.
            chunks.append(ChunkDraft(text=f"{header}\n{line}"))
    return chunks

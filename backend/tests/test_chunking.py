from pathlib import Path

from app.rag.chunking import is_junk_filename, parse_case_table, parse_generic_csv_table, parse_transcript_csv

FIXTURES = Path(__file__).parent / "fixtures"


def test_junk_filename_detected():
    assert is_junk_filename("._Taglio_Mariam_guida_tecnica_md.docx")
    assert not is_junk_filename("Taglio_Mariam_guida_tecnica_md.docx")


def test_parse_comma_delimited_transcript():
    raw = (FIXTURES / "sample_comma.csv").read_bytes()
    chunks = parse_transcript_csv(raw, target_chars=900, overlap_chars=100)

    assert len(chunks) == 1  # righe brevi, entrano in un solo chunk
    assert chunks[0].start_timestamp == "00:00:04"  # normalizzato da HH:MM:SS:FF a HH:MM:SS
    assert "croce" in chunks[0].text


def test_parse_semicolon_delimited_transcript_ignores_duplicate_column():
    raw = (FIXTURES / "sample_semicolon.csv").read_bytes()
    chunks = parse_transcript_csv(raw, target_chars=900, overlap_chars=100)

    assert len(chunks) == 1
    # il testo non deve comparire due volte (colonna 'Testo completo' duplicata va ignorata)
    assert chunks[0].text.count("miscela di doratura") == 1


def test_parse_semicolon_transcript_with_long_multiline_quoted_field():
    # Bug reale: quando il campo "Testo completo" contiene interruzioni di riga
    # ed è più lungo dei 2048 caratteri campionati per il rilevamento del
    # delimitatore, il campione conteneva una virgoletta spaiata (sniff falliva)
    # e il fallback contava virgole/punti-e-virgola su tutto il campione,
    # scegliendo ',' invece di ';' a causa delle virgole nella prosa italiana.
    raw = (FIXTURES / "sample_semicolon_long_quoted_field.csv").read_bytes()
    chunks = parse_transcript_csv(raw, target_chars=5000, overlap_chars=100)

    assert len(chunks) == 1
    assert chunks[0].start_timestamp == "00:00:05"
    assert chunks[0].end_timestamp == "00:00:20"
    assert "Applico la mousse sulla parte superiore." in chunks[0].text
    assert "Poi lavoro le lunghezze e le punte." in chunks[0].text


def test_transcript_chunking_respects_target_size_and_overlap():
    raw = (FIXTURES / "sample_comma.csv").read_bytes()
    chunks = parse_transcript_csv(raw, target_chars=60, overlap_chars=20)

    assert len(chunks) > 1
    for c in chunks:
        assert c.start_timestamp is not None


def test_generic_csv_table_ignores_empty_trailing_columns():
    raw = (FIXTURES / "sample_product_table.csv").read_bytes()
    chunks = parse_generic_csv_table(raw)

    assert len(chunks) == 2
    assert "Linea: Repair Care" in chunks[0].text
    assert "Prodotto: Shampoo" in chunks[0].text
    assert "mirtillo rosso" in chunks[0].text
    # le due colonne senza intestazione (";;") non devono comparire come "': ...'"
    assert ": ." not in chunks[0].text


def test_transcript_csv_returns_empty_for_product_table():
    # Deve tornare lista vuota (non un errore): ingest.py userà questo per
    # capire che il file va analizzato con il parser tabellare generico.
    raw = (FIXTURES / "sample_product_table.csv").read_bytes()
    chunks = parse_transcript_csv(raw, target_chars=900, overlap_chars=100)
    assert chunks == []


def test_case_table_one_row_per_case():
    raw = (FIXTURES / "sample_cases.txt").read_bytes()
    chunks = parse_case_table(raw)

    assert len(chunks) == 3
    assert all("Caso 00" in c.text for c in chunks)
    # il contesto/formato deve essere anteposto a ogni chunk isolato
    assert "Formato:" in chunks[0].text
    assert "Formato:" in chunks[2].text

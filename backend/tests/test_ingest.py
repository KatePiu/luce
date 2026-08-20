from app.rag.ingest import _guess_origin_kind


def test_docx_with_casi_in_name_is_guide_doc_not_case_table():
    # Bug reale: un .docx con "casi" nel nome veniva letto come tabella di
    # testo semplice invece che come documento Word, producendo zero contenuto.
    assert _guess_origin_kind("Casi_particolari_md.docx") == "guide_doc"


def test_txt_with_casi_in_name_is_case_table():
    assert _guess_origin_kind("Casi_particolari_md.txt") == "case_table"


def test_csv_is_always_transcript_csv():
    assert _guess_origin_kind("Casi_particolari.csv") == "transcript_csv"


def test_plain_docx_guide_is_guide_doc():
    assert _guess_origin_kind("Taglio_Mariam_guida_tecnica_md.docx") == "guide_doc"


def test_product_sheet_txt_still_detected():
    assert _guess_origin_kind("AMO_scheda_prodotto.txt") == "product_sheet"

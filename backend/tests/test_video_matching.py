from app.rag.retrieval import _extract_technique_number, _keywords


def test_keywords_ignores_stopwords_and_short_words():
    words = _keywords("Come si fa la piega con il phon per capelli ricci?")
    assert "piega" in words
    assert "phon" in words
    assert "capelli" in words
    assert "ricci" in words
    # stopword/troppo corte: non devono comparire
    assert "come" not in words
    assert "si" not in words
    assert "la" not in words
    assert "il" not in words


def test_keywords_overlap_matches_relevant_video_title():
    query_words = _keywords("Cerco il video sullo shatush biondo")
    title_words = _keywords("04 - HENNE SHATUSH - BIONDO")
    overlap = query_words & title_words
    assert "shatush" in overlap
    assert "biondo" in overlap


def test_keywords_overlap_empty_for_unrelated_title():
    query_words = _keywords("Come si prepara una piega")
    title_words = _keywords("INFUSION MOUSSE REPAIR")
    assert not (query_words & title_words)


def test_extract_technique_number_from_question_with_brand_between():
    # Bug reale: "tecnica" e il numero non sono sempre adiacenti nella domanda
    # (es. il nome della serie si infila in mezzo), a differenza dei titoli dei
    # file dove sono sempre vicini.
    assert _extract_technique_number("Quali sono i passaggi della tecnica Infusion n°2?") == "2"
    assert _extract_technique_number("Come si prepara la tecnica Infusion numero 2?") == "2"


def test_extract_technique_number_from_filename_with_underscore():
    # "\b" non avrebbe funzionato qui: "_" è un carattere di parola, quindi non
    # crea un confine di parola prima di "Tecnica".
    assert _extract_technique_number("Infusion_Tecnica_2_Guida_md.docx") == "2"
    assert _extract_technique_number("04 - INFUSION - TECNICA n°3.csv") == "3"


def test_extract_technique_number_returns_none_without_technique_mention():
    assert _extract_technique_number("Mediterranean Complex a cosa serve?") is None
    assert _extract_technique_number("Piega_Mariam_guida_tecnica_md.docx") is None

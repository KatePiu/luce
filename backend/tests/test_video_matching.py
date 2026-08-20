from app.rag.retrieval import _keywords


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

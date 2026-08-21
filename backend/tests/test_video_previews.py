from app.rag.video_previews import VIDEO_PREVIEW_MAP, match_preview_url


def test_mapping_has_all_32_entries_from_the_spec_document():
    assert len(VIDEO_PREVIEW_MAP) == 32


def test_matches_title_with_mp4_extension_stripped():
    assert match_preview_url("VIDEO LINEA SHATUSH COMPLETA.mp4") == VIDEO_PREVIEW_MAP["VIDEO LINEA SHATUSH COMPLETA"]


def test_matches_title_with_double_extension_stripped():
    # Caso reale trovato in produzione: titolo con doppia estensione nel nome del file.
    assert match_preview_url("NATURA MAGICA.mov.mp4") == VIDEO_PREVIEW_MAP["NATURA MAGICA"]


def test_matches_case_insensitive_and_trims_whitespace():
    assert match_preview_url("  taglio mariam  ") == VIDEO_PREVIEW_MAP["TAGLIO MARIAM"]


def test_no_match_returns_none_instead_of_guessing():
    assert match_preview_url("Un video che non è nella mappatura") is None


def test_preview_url_is_correctly_url_encoded():
    url = VIDEO_PREVIEW_MAP["02 - INFUSION - TECNICA n°1"]
    assert url == "https://www.360maker.it/Luce/anteprime_video/02%20-%20INFUSION%20-%20TECNICA%20n%C2%B01.png"

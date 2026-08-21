from app.rag import groundedness
from app.rag.groundedness import check_claims_with_model, check_structural, extract_cited_sources
from app.rag.retrieval import RetrievedChunk


def _chunk(chunk_id: str, source_id: str = "src-1") -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source_id=source_id,
        source_title="Henne Castano",
        video_id="video-1",
        video_title="04 - HENNE SHATUSH - CASTANO",
        video_url="https://drive.google.com/x",
        video_platform="drive",
        document_url=None,
        start_timestamp="00:06:06",
        end_timestamp=None,
        text="testo di esempio",
        score=0.8,
    )


def test_extract_cited_sources_parses_block():
    raw = 'Ecco la procedura.\n<cited_sources>["c1", "c2"]</cited_sources>'
    visible, ids = extract_cited_sources(raw)
    assert visible == "Ecco la procedura."
    assert ids == ["c1", "c2"]


def test_extract_cited_sources_handles_missing_block():
    visible, ids = extract_cited_sources("Serve una domanda di chiarimento.")
    assert visible == "Serve una domanda di chiarimento."
    assert ids == []


def test_structural_check_fails_when_procedure_has_no_citation():
    result = check_structural("Si può procedere con i passaggi operativi seguenti...", [], [_chunk("c1")])
    assert not result.passed


def test_structural_check_fails_on_invented_chunk_id():
    result = check_structural("Si può procedere.", ["c-inventato"], [_chunk("c1")])
    assert not result.passed
    assert "c-inventato" in result.reason


def test_structural_check_passes_with_valid_citation():
    result = check_structural("Si può procedere con questi passaggi operativi.", ["c1"], [_chunk("c1")])
    assert result.passed


def test_structural_check_passes_for_clarifying_question_without_citation():
    result = check_structural("Qual è il colore naturale della cliente?", [], [_chunk("c1")])
    assert result.passed




def test_check_claims_retries_once_after_a_spurious_fail(monkeypatch):
    # Bug reale: la stessa risposta, verificata due volte, dava una volta PASS e una volta
    # FAIL — un singolo FAIL non deve bastare a bocciare una risposta altrimenti corretta.
    responses = iter(
        [
            '{"verdict": "FAIL", "unsupported_claims": ["tempo di posa"]}',
            '{"verdict": "PASS", "unsupported_claims": []}',
        ]
    )
    calls = []

    def fake_call_claude(**kwargs):
        calls.append(kwargs)
        return next(responses)

    monkeypatch.setattr(groundedness, "call_claude", fake_call_claude)
    result = check_claims_with_model("Si può procedere con questi passaggi operativi.", [_chunk("c1")])
    assert result.passed
    assert len(calls) == 2


def test_check_claims_fails_only_after_two_consecutive_fails(monkeypatch):
    def fake_call_claude(**kwargs):
        return '{"verdict": "FAIL", "unsupported_claims": ["tempo di posa"]}'

    monkeypatch.setattr(groundedness, "call_claude", fake_call_claude)
    result = check_claims_with_model("Si può procedere con questi passaggi operativi.", [_chunk("c1")])
    assert not result.passed

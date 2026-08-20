from app.rag.retrieval import RetrievedChunk, detect_conflict


def _chunk(source_id: str, score: float) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=f"chunk-{source_id}-{score}",
        source_id=source_id,
        source_title=f"Fonte {source_id}",
        video_title=None,
        video_url=None,
        video_platform=None,
        document_url=None,
        start_timestamp=None,
        end_timestamp=None,
        text="testo",
        score=score,
    )


def test_no_conflict_when_second_source_is_below_reliability_threshold():
    # Bug reale: una domanda su una procedura ben coperta da un'unica guida
    # (punteggio migliore comunque sotto soglia, es. 0.54) veniva segnalata
    # come "conflitto" solo perché un secondo chunk irrilevante, altrettanto
    # mediocre, aveva un punteggio vicino — pur essendo entrambi troppo deboli
    # per essere considerati affidabili.
    chunks = [_chunk("a", 0.54), _chunk("b", 0.52)]
    assert detect_conflict(chunks) is None


def test_no_conflict_when_close_chunk_is_below_threshold_even_if_top_is_high():
    chunks = [_chunk("a", 0.80), _chunk("b", 0.50)]
    assert detect_conflict(chunks) is None


def test_conflict_when_both_chunks_are_reliable_and_close():
    chunks = [_chunk("a", 0.70), _chunk("b", 0.68)]
    conflicting = detect_conflict(chunks)
    assert conflicting is not None
    assert conflicting.source_id == "b"


def test_no_conflict_when_close_chunk_is_same_source():
    chunks = [_chunk("a", 0.70), _chunk("a", 0.69)]
    assert detect_conflict(chunks) is None


def test_no_conflict_when_scores_are_far_apart():
    chunks = [_chunk("a", 0.85), _chunk("b", 0.60)]
    assert detect_conflict(chunks) is None

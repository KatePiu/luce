from app.rag.retrieval import RetrievedChunk, detect_conflict, sort_by_relevance_then_richness


def _chunk(source_id: str, score: float, text: str = "testo") -> RetrievedChunk:
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
        text=text,
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
    chunks = [
        _chunk("a", 0.70, "Per la miscela servono due misurini di rosso e due di emolliente."),
        _chunk("b", 0.68, "Il taglio si esegue partendo dalle punte su capelli asciutti."),
    ]
    conflicting = detect_conflict(chunks)
    assert conflicting is not None
    assert conflicting.source_id == "b"


def test_no_conflict_when_close_chunk_is_same_source():
    chunks = [_chunk("a", 0.70), _chunk("a", 0.69)]
    assert detect_conflict(chunks) is None


def test_no_conflict_when_scores_are_far_apart():
    chunks = [_chunk("a", 0.85), _chunk("b", 0.60)]
    assert detect_conflict(chunks) is None


def test_no_conflict_when_sources_agree_despite_different_wording():
    # Bug reale: una guida caricata due volte con un nome file quasi identico
    # (stesso contenuto) veniva segnalata come "in conflitto con se stessa".
    text_a = "Per la miscela di doratura servono due misurini di rosso normale e due misurini di emolliente."
    text_b = "Per creare la miscela dorata occorrono due misurini di rosso normale più due misurini di emolliente."
    chunks = [_chunk("a", 0.70, text_a), _chunk("b", 0.69, text_b)]
    assert detect_conflict(chunks) is None


def test_conflict_when_reliable_sources_disagree_on_different_topics():
    text_a = "Per la miscela di doratura servono due misurini di rosso normale e due di emolliente."
    text_b = "Il taglio si esegue partendo dalle punte con tecnica a scalare su capelli asciutti."
    chunks = [_chunk("a", 0.70, text_a), _chunk("b", 0.68, text_b)]
    conflicting = detect_conflict(chunks)
    assert conflicting is not None
    assert conflicting.source_id == "b"


def test_sort_prefers_richer_content_at_equal_rounded_relevance():
    # A parità di punteggio arrotondato, la fonte con più parole chiave (più
    # completa) deve comparire prima, invece di dipendere dall'ordine casuale
    # con cui i risultati arrivano dal database.
    sparse = _chunk("a", 0.701, "due misurini di rosso")
    rich = _chunk("b", 0.699, "due misurini di rosso normale e due misurini di emolliente per la miscela di doratura")
    ordered = sort_by_relevance_then_richness([sparse, rich])
    assert ordered[0].source_id == "b"


def test_sort_keeps_relevance_as_primary_key():
    clearly_better = _chunk("a", 0.90, "testo breve")
    clearly_worse_but_longer = _chunk("b", 0.40, "testo molto più lungo con molte parole chiave diverse qui dentro")
    ordered = sort_by_relevance_then_richness([clearly_worse_but_longer, clearly_better])
    assert ordered[0].source_id == "a"

"""Orchestrazione del flusso RAG: ricezione domanda -> recupero -> controllo soglia ->
generazione vincolata -> controlli anti-allucinazione -> risposta con fonti, o escalation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.integrations.anthropic_client import call_claude
from app.rag.groundedness import run_groundedness_checks
from app.rag.prompt import SYSTEM_PROMPT
from app.rag.retrieval import (
    RetrievedChunk,
    VideoCandidate,
    detect_conflict,
    find_candidate_videos,
    is_sufficient,
    retrieve_with_priority,
    sort_by_relevance_then_richness,
)

INSUFFICIENT_MATERIALS_MESSAGE = (
    "Nei materiali dell'Accademia non ho trovato informazioni sufficienti per "
    "rispondere con sicurezza a questo caso. Posso raccogliere i dettagli e "
    "inoltrare la richiesta a un tutor umano."
)

LOW_CONFIDENCE_NOTE = (
    "ATTENZIONE — PERTINENZA BASSA: i passaggi qui sotto hanno un punteggio di somiglianza "
    "con l'ULTIMO messaggio piuttosto basso (la ricerca guarda solo l'ultimo messaggio, non "
    "tutta la conversazione). Questo capita spesso con risposte brevi di chiarimento (es. "
    "\"Arancione.\", \"Radice.\") che da sole dicono poco, anche quando la conversazione nel "
    "suo complesso sta procedendo bene: NON è un segnale che manca qualcosa di nuovo, è solo "
    "un limite della ricerca automatica su un messaggio breve. NON dichiarare i materiali "
    "insufficienti e NON ripetere l'ultima domanda di chiarimento già fatta: rileggi la "
    "conversazione, riconosci cosa hai già capito, e fai la domanda successiva della "
    "sequenza diagnostica (o rispondi, se ormai hai abbastanza informazioni) — mai la stessa "
    "domanda del turno precedente.\n\n"
)

AMBIGUITY_NOTE = (
    "ATTENZIONE — POSSIBILE AMBIGUITÀ NEI PASSAGGI RECUPERATI: due passaggi pertinenti a "
    "questa domanda sembrano dare indicazioni diverse. Prima di rispondere, valuta se si "
    "tratta in realtà di scenari/casi diversi (es. una condizione specifica della cliente "
    "non ancora chiarita dalla domanda — come nel caso che ha portato a questa regola: "
    "capelli bianchi concentrati in una zona vs sparsi su tutta la testa, con indicazioni "
    "diverse sull'uso del pigmento). Se è così, fai la domanda di chiarimento necessaria "
    "per capire quale caso si applica, invece di scegliere una delle due indicazioni a "
    "caso o di dichiarare genericamente che le fonti sono in conflitto. Solo se, leggendo "
    "con attenzione, le fonti risultano davvero in contraddizione sullo stesso identico "
    "caso, dillo esplicitamente e proponi l'inoltro a un tutor umano.\n\n"
)


@dataclass
class CitedSource:
    source_id: str
    title: str
    video_title: str | None
    video_url: str | None
    video_platform: str | None
    document_url: str | None
    start_timestamp: str | None


@dataclass
class AnswerResult:
    text: str
    escalate: bool
    escalation_reason: str | None = None
    retrieval_score: float | None = None
    cited_sources: list[CitedSource] = field(default_factory=list)


def _format_chunk(c: RetrievedChunk) -> str:
    meta = f"[chunk_id={c.chunk_id} | fonte=\"{c.source_title}\""
    if c.video_title:
        meta += f" | video=\"{c.video_title}\""
    if c.start_timestamp:
        meta += f" | timestamp={c.start_timestamp}"
    meta += "]"
    return f"{meta}\n{c.text}"


def _build_context_block(priority: list[RetrievedChunk], general: list[RetrievedChunk], videos: list[VideoCandidate]) -> str:
    sections = []
    if priority:
        sections.append(
            "== FONTI PRIORITARIE — CASI PARTICOLARI (dare precedenza a queste per problemi di "
            "colorazione, correzioni, risultati non corretti, situazioni anomale) ==\n\n"
            + "\n\n---\n\n".join(_format_chunk(c) for c in priority)
        )
    if general:
        sections.append(
            "== ALTRE FONTI PERTINENTI (guide, prodotti, procedure) ==\n\n"
            + "\n\n---\n\n".join(_format_chunk(c) for c in general)
        )
    if videos:
        video_lines = "\n".join(f'- video_id={v.video_id} | titolo="{v.title}" | link={v.url}' for v in videos)
        sections.append(
            "== VIDEO INDICIZZATI SOLO PER TITOLO (nessuna trascrizione disponibile: non descriverne "
            "il contenuto, puoi solo segnalare che il titolo sembra pertinente e proporne il link) ==\n\n"
            + video_lines
        )
    return "\n\n".join(sections)


def _resolve_cited_sources(cited_ids: list[str], retrieved: list[RetrievedChunk]) -> list[CitedSource]:
    by_id = {c.chunk_id: c for c in retrieved}
    seen_sources: set[str] = set()
    out: list[CitedSource] = []
    for cid in cited_ids:
        chunk = by_id.get(cid)
        if not chunk or chunk.source_id in seen_sources:
            continue
        seen_sources.add(chunk.source_id)
        out.append(
            CitedSource(
                source_id=chunk.source_id,
                title=chunk.source_title,
                video_title=chunk.video_title,
                video_url=chunk.video_url,
                video_platform=chunk.video_platform,
                document_url=chunk.document_url,
                start_timestamp=chunk.start_timestamp,
            )
        )
    return out


def answer_question(
    db: Session,
    question: str,
    history: list[dict] | None = None,
) -> AnswerResult:
    priority, general = retrieve_with_priority(db, question)
    combined = sort_by_relevance_then_richness(priority + general)

    videos = find_candidate_videos(db, question)

    # Nessun passaggio e nessun video: non c'è nulla su cui far ragionare il modello,
    # a prescindere da quanto la domanda sia vaga o precisa — unico caso in cui si
    # rinuncia a generare senza nemmeno provare.
    if not combined and not videos:
        return AnswerResult(
            text=INSUFFICIENT_MATERIALS_MESSAGE,
            escalate=True,
            escalation_reason="no_sources",
            retrieval_score=None,
        )

    # Un punteggio basso spesso significa solo che la domanda è troppo generica per essere
    # confrontata bene con i materiali (es. "quanto ne devo mettere?" senza dire il prodotto)
    # — non che l'argomento sia davvero scoperto. Bloccare qui, prima ancora di chiamare il
    # modello, impedirebbe al tutor AI di fare la cosa giusta in questi casi: fare una
    # domanda di chiarimento mirata invece di arrendersi subito. Si segnala quindi la bassa
    # pertinenza al modello e si lascia che segua il protocollo (chiarisci, poi ricontrolla).
    low_confidence = not is_sufficient(combined)

    # Un punteggio vicino tra fonti diverse con contenuto diverso non significa sempre una
    # vera contraddizione: spesso sono scenari/casi diversi nello stesso materiale (es. due
    # pattern diversi di capelli bianchi, con indicazioni diverse). Invece di bloccare subito
    # la risposta, si segnala l'ambiguità al modello e si lascia che ragioni — chiedendo un
    # chiarimento se serve, spiegando la distinzione se i passaggi lo permettono, o dichiarando
    # un conflitto reale solo se, leggendo il contesto, lo è davvero. Il controllo di
    # groundedness dopo la generazione resta comunque la rete di sicurezza finale.
    conflicting = None if low_confidence else detect_conflict(combined)

    context_block = _build_context_block(priority, general, videos)
    if conflicting:
        context_block = AMBIGUITY_NOTE + context_block
    if low_confidence:
        context_block = LOW_CONFIDENCE_NOTE + context_block
    user_message = f"CONTESTO RECUPERATO DAI MATERIALI DELL'ACCADEMIA:\n\n{context_block}\n\nDOMANDA DEL PARRUCCHIERE:\n{question}"

    raw_response = call_claude(system=SYSTEM_PROMPT, user_message=user_message, history=history)

    result = run_groundedness_checks(raw_response, combined)
    if not result.passed:
        return AnswerResult(
            text=INSUFFICIENT_MATERIALS_MESSAGE,
            escalate=True,
            escalation_reason="insufficient_sources",
            retrieval_score=combined[0].score if combined else None,
        )

    cited_sources = _resolve_cited_sources(result.cited_chunk_ids or [], combined)
    return AnswerResult(
        text=result.visible_text,
        escalate=False,
        retrieval_score=combined[0].score if combined else None,
        cited_sources=cited_sources,
    )


def debug_answer_question(db: Session, question: str) -> dict:
    """Come `answer_question`, ma espone i passaggi interni (usato solo dall'endpoint
    diagnostico admin) — in particolare la risposta grezza del modello e il motivo esatto
    di un eventuale rifiuto del controllo di groundedness, altrimenti scartato."""
    priority, general = retrieve_with_priority(db, question)
    combined = sort_by_relevance_then_richness(priority + general)
    videos = find_candidate_videos(db, question)

    if not combined and not videos:
        return {"stage": "no_sources_before_generation", "combined_top_score": None}

    low_confidence = not is_sufficient(combined)
    conflicting = None if low_confidence else detect_conflict(combined)
    context_block = _build_context_block(priority, general, videos)
    if conflicting:
        context_block = AMBIGUITY_NOTE + context_block
    if low_confidence:
        context_block = LOW_CONFIDENCE_NOTE + context_block

    user_message = f"CONTESTO RECUPERATO DAI MATERIALI DELL'ACCADEMIA:\n\n{context_block}\n\nDOMANDA DEL PARRUCCHIERE:\n{question}"
    raw_response = call_claude(system=SYSTEM_PROMPT, user_message=user_message)
    result = run_groundedness_checks(raw_response, combined)

    return {
        "stage": "generated",
        "low_confidence": low_confidence,
        "ambiguity_flagged": bool(conflicting),
        "conflicting_with": conflicting.source_title if conflicting else None,
        "raw_response": raw_response,
        "groundedness_passed": result.passed,
        "groundedness_reason": result.reason,
    }

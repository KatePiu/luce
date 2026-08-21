"""Gestione della scheda diagnostica strutturata (`Case`) di una conversazione —
Specifica_Definitiva_Tutor_AI, tabella 2 "Scheda diagnostica standard" e macchina a stati
del caso (punto 12). Un caso per conversazione: i campi vengono aggiornati, non
sovrascritti a vuoto, via via che la diagnosi procede."""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Case, Chunk, Conversation, Feedback, Message, Source
from app.rag.case_extraction import CASE_FIELDS, extract_case_fields
from app.rag.embeddings import embed_texts
from app.rag.generate import CitedSource
from app.rag.ingest import get_or_create_technique
from app.rag.retrieval import VALIDATED_CASES_SLUG

logger = logging.getLogger(__name__)

_CASE_FIELD_LABELS = {
    "area": "Area",
    "tecnica": "Tecnica",
    "base_partenza": "Base di partenza",
    "capelli_bianchi": "Capelli bianchi",
    "storico_tecnico": "Storico tecnico",
    "porosita": "Porosità",
    "servizio_eseguito": "Servizio eseguito",
    "formula_prodotti": "Formula/prodotti",
    "tempi_condizioni": "Tempi/condizioni",
    "problema_osservato": "Problema osservato",
    "zona_coinvolta": "Zona coinvolta",
    "risultato_desiderato": "Risultato desiderato",
    "risultato_reale": "Risultato reale",
}

# Mappa tipo di feedback -> nuovo stato del caso (Specifica_Definitiva_Tutor_AI, tabella 4
# e punto 14 "Flusso di apprendimento"). "mi_e_stata_utile" è un segnale leggero sulla
# risposta, non una conferma di esito: non fa avanzare lo stato da solo. Il documento non
# prevede uno stato dedicato per "parzialmente risolto": viene trattato come NON_RISOLTO ai
# fini della macchina a stati, mantenendo la sfumatura nel campo `esito` in chiaro.
FEEDBACK_STATE_MAP = {
    "mi_e_stata_utile": None,
    "non_ha_risolto_il_problema": "NON_RISOLTO",
    "problema_risolto": "DA_VALIDARE",
    "problema_parzialmente_risolto": "NON_RISOLTO",
    "problema_non_risolto": "NON_RISOLTO",
    "risposta_non_corretta": "NON_RISOLTO",
    "ho_dovuto_contattare_il_tutor": "ESCALATION_TUTOR",
}

FEEDBACK_ESITO_MAP = {
    "mi_e_stata_utile": "utile",
    "non_ha_risolto_il_problema": "non risolto",
    "problema_risolto": "risolto",
    "problema_parzialmente_risolto": "parzialmente risolto",
    "problema_non_risolto": "non risolto",
    "risposta_non_corretta": "risposta non corretta",
    "ho_dovuto_contattare_il_tutor": "richiesto tutor umano",
}


def _confidence_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= 0.7:
        return "alto"
    if score >= 0.55:
        return "medio"
    return "basso"


def upsert_case_from_conversation(
    db: Session,
    conversation: Conversation,
    history: list[dict],
    escalate: bool,
    cited_sources: list[CitedSource],
    retrieval_score: float | None,
) -> Case | None:
    """Aggiorna (o crea) la scheda diagnostica della conversazione. Un fallimento
    dell'estrazione non deve mai bloccare la risposta della chat: eventuali errori vengono
    solo loggati, la funzione ritorna None e il chiamante prosegue normalmente."""
    try:
        extracted = extract_case_fields(history)
    except Exception:
        logger.exception("Estrazione della scheda diagnostica fallita per la conversazione %s", conversation.id)
        return None

    case = db.query(Case).filter(Case.conversation_id == conversation.id).one_or_none()
    if case is None:
        case = Case(conversation_id=conversation.id)
        db.add(case)

    if extracted:
        for field in CASE_FIELDS:
            value = extracted.get(field)
            if value:
                setattr(case, field, value)

    if cited_sources:
        case.fonti_trovate = [s.title for s in cited_sources]
    case.livello_confidenza = _confidence_label(retrieval_score)
    case.stato = "ESCALATION_TUTOR" if escalate else "IN_ATTESA_DI_FEEDBACK"

    db.commit()
    db.refresh(case)
    return case


def apply_feedback(db: Session, message: Message, tipo: str, nota: str | None) -> tuple[Feedback, Case | None]:
    """Registra un feedback su un messaggio outbound del tutor AI e aggiorna lo stato del
    caso collegato di conseguenza (tabella 4). Ritorna (feedback, caso_aggiornato_o_None)."""
    case = db.query(Case).filter(Case.conversation_id == message.conversation_id).one_or_none()

    feedback = Feedback(case_id=case.id if case else None, message_id=message.id, tipo=tipo, nota=nota)
    db.add(feedback)

    if case is not None:
        case.esito = FEEDBACK_ESITO_MAP.get(tipo)
        new_stato = FEEDBACK_STATE_MAP.get(tipo)
        if new_stato:
            case.stato = new_stato

    db.commit()
    db.refresh(feedback)
    if case is not None:
        db.refresh(case)
    return feedback, case


def _case_content_text(db: Session, case: Case) -> str:
    """Testo da incorporare per il caso validato: la scheda diagnostica in chiaro (per il
    controllo di compatibilità, punto 15) seguita dall'ultima risposta esplicita del tutor
    AI/umano nella conversazione — la Specifica_Definitiva_Tutor_AI (punto 13) richiede che
    un precedente riutilizzabile abbia "risposta o procedura esplicita", non solo i campi."""
    righe = [
        f"{_CASE_FIELD_LABELS[field]}: {getattr(case, field)}" for field in CASE_FIELDS if getattr(case, field)
    ]
    scheda = "\n".join(righe)

    last_outbound = (
        db.query(Message)
        .filter(Message.conversation_id == case.conversation_id, Message.direction == "outbound")
        .order_by(Message.created_at.desc())
        .first()
    )
    risposta = last_outbound.body if last_outbound and last_outbound.body else ""

    return f"CASO VALIDATO\n{scheda}\n\nRisposta confermata:\n{risposta}".strip()


def promote_case_to_knowledge(db: Session, case: Case, admin_id) -> Source:
    """Promuove un caso a Knowledge riutilizzabile (stato VALIDATO_PER_KNOWLEDGE): crea una
    fonte dedicata (tecnica "casi_validati", livello 4 della gerarchia) con il contenuto del
    caso incorporato, così diventa recuperabile per domande future compatibili. Non è mai
    automatico: richiede sempre un'azione esplicita di un admin/tutor (Specifica_Definitiva_
    Tutor_AI, punto 13 "Regola di promozione")."""
    text = _case_content_text(db, case)
    embedding = embed_texts([text])[0]

    technique = get_or_create_technique(db, VALIDATED_CASES_SLUG, label="Casi validati")
    title = case.problema_osservato or case.area or f"Caso {case.id}"
    source = Source(
        title=f"Caso validato: {title}"[:200],
        technique_id=technique.id,
        origin_filename=f"caso_validato_{case.id}.txt",
        origin_kind="guide_doc",
        uploaded_by=admin_id,
    )
    db.add(source)
    db.flush()

    db.add(Chunk(source_id=source.id, seq=0, text=text, embedding=embedding))

    case.stato = "VALIDATO_PER_KNOWLEDGE"
    case.validated_by = admin_id
    case.validated_at = func.now()
    case.promoted_source_id = source.id

    db.commit()
    db.refresh(source)
    return source


def declassify_case(db: Session, case: Case) -> None:
    """Ritira/declassa un caso: disattiva la fonte promossa (se esiste — mai cancellata,
    solo disattivata, come per tutte le altre fonti) e riporta il caso a uno stato che
    riconosce l'esito positivo confermato senza però tenerlo come Knowledge riutilizzabile.
    Serve sia per rifiutare un candidato DA_VALIDARE sia per ritirare un caso già
    VALIDATO_PER_KNOWLEDGE che risulta non più corretto (punto 20 del documento)."""
    if case.promoted_source_id:
        source = db.get(Source, case.promoted_source_id)
        if source:
            source.status = "disabled"

    case.stato = "RISOLTO_DA_AI"
    case.validated_by = None
    case.validated_at = None
    case.promoted_source_id = None

    db.commit()


def case_to_diagnostic_dict(case: Case | None) -> dict:
    """Formatta la scheda come la tabella 3 del documento ("Dato da inviare al tutor"),
    per l'escalation — usato sia per lo snapshot salvato sia per il corpo dell'email."""
    if case is None:
        return {}
    return {
        "problema_sintetico": case.problema_osservato,
        "area": case.area,
        "tecnica": case.tecnica,
        "base_partenza": case.base_partenza,
        "capelli_bianchi": case.capelli_bianchi,
        "storico_tecnico": case.storico_tecnico,
        "porosita": case.porosita,
        "servizio_eseguito": case.servizio_eseguito,
        "formula_prodotti": case.formula_prodotti,
        "tempi_condizioni": case.tempi_condizioni,
        "risultato_desiderato": case.risultato_desiderato,
        "risultato_reale": case.risultato_reale,
        "zona_coinvolta": case.zona_coinvolta,
        "fonti_trovate": case.fonti_trovate,
        "livello_confidenza": case.livello_confidenza,
    }

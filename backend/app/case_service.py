"""Gestione della scheda diagnostica strutturata (`Case`) di una conversazione —
Specifica_Definitiva_Tutor_AI, tabella 2 "Scheda diagnostica standard" e macchina a stati
del caso (punto 12). Un caso per conversazione: i campi vengono aggiornati, non
sovrascritti a vuoto, via via che la diagnosi procede."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.models import Case, Conversation
from app.rag.case_extraction import CASE_FIELDS, extract_case_fields
from app.rag.generate import CitedSource

logger = logging.getLogger(__name__)


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

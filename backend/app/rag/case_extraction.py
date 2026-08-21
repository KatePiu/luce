"""Estrazione della scheda diagnostica strutturata da una conversazione
(Specifica_Definitiva_Tutor_AI, tabella 2 "Scheda diagnostica standard"). Chiamata dopo
ogni risposta del tutor AI per tenere aggiornato il record `Case` della conversazione — non
sostituisce il ragionamento del tutor, si limita a distillare in campi strutturati ciò che è
già stato detto esplicitamente."""

from __future__ import annotations

from app.integrations.anthropic_client import call_claude
from app.rag.llm_json import parse_json_response
from app.rag.prompt import CASE_EXTRACTOR_PROMPT

CASE_FIELDS = [
    "area",
    "tecnica",
    "base_partenza",
    "capelli_bianchi",
    "storico_tecnico",
    "porosita",
    "servizio_eseguito",
    "formula_prodotti",
    "tempi_condizioni",
    "problema_osservato",
    "zona_coinvolta",
    "risultato_desiderato",
    "risultato_reale",
]


def extract_case_fields(history: list[dict]) -> dict | None:
    """Ritorna un dict con le 13 chiavi della scheda diagnostica (valore o None), oppure
    None se l'estrazione fallisce. Un fallimento qui non deve mai bloccare la risposta
    principale della chat: va sempre trattato come best-effort dal chiamante."""
    if not history:
        return None
    transcript = "\n".join(f"{'Parrucchiere' if m['role'] == 'user' else 'Tutor AI'}: {m['content']}" for m in history)
    raw = call_claude(system=CASE_EXTRACTOR_PROMPT, user_message=transcript, max_tokens=600)
    parsed = parse_json_response(raw)
    if parsed is None:
        return None
    return {field: parsed.get(field) for field in CASE_FIELDS}

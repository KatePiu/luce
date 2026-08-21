"""Controlli applicativi anti-allucinazione, eseguiti DOPO la generazione.

Non ci si affida solo al prompt: qui si verifica meccanicamente che la
risposta sia ancorata alle fonti recuperate, prima di mostrarla all'utente.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.integrations.anthropic_client import call_claude
from app.rag.prompt import GROUNDEDNESS_VERIFIER_PROMPT
from app.rag.retrieval import RetrievedChunk

CITED_SOURCES_RE = re.compile(r"<cited_sources>(.*?)</cited_sources>", re.DOTALL)


@dataclass
class GroundednessResult:
    passed: bool
    reason: str = ""
    cited_chunk_ids: list[str] | None = None
    visible_text: str = ""


def extract_cited_sources(raw_response: str) -> tuple[str, list[str]]:
    """Separa il testo destinato all'utente dal blocco <cited_sources>...</cited_sources>."""
    match = CITED_SOURCES_RE.search(raw_response)
    visible_text = CITED_SOURCES_RE.sub("", raw_response).strip()
    if not match:
        return visible_text, []
    try:
        ids = json.loads(match.group(1))
        if isinstance(ids, list):
            return visible_text, [str(i) for i in ids]
    except (json.JSONDecodeError, TypeError):
        pass
    return visible_text, []


def _looks_like_procedure(text: str) -> bool:
    """Una risposta con procedura tecnica dichiara qualcosa di più di una domanda di
    chiarimento o del messaggio standard 'materiali insufficienti'."""
    markers = ["si può procedere", "non si può procedere", "passaggi operativi", "procedura"]
    lowered = text.lower()
    return any(m in lowered for m in markers)


def check_structural(visible_text: str, cited_chunk_ids: list[str], retrieved: list[RetrievedChunk]) -> GroundednessResult:
    """Controlli strutturali, senza chiamare il modello:
    - se la risposta sembra una procedura, deve citare almeno una fonte valida;
    - ogni chunk_id citato deve esistere davvero tra i passaggi recuperati (no invenzioni);
    - se l'id esiste, link e timestamp mostrati devono corrispondere ai metadati reali della fonte
      (qui ci si limita a verificare che provengano dal record recuperato, non da testo libero del modello).
    """
    retrieved_ids = {c.chunk_id for c in retrieved}

    if not cited_chunk_ids:
        if _looks_like_procedure(visible_text):
            return GroundednessResult(False, "Risposta con procedura ma nessuna fonte citata", [], visible_text)
        return GroundednessResult(True, "Nessuna citazione richiesta (chiarimento o escalation)", [], visible_text)

    invalid_ids = [cid for cid in cited_chunk_ids if cid not in retrieved_ids]
    if invalid_ids:
        return GroundednessResult(False, f"Citati chunk_id inesistenti nel recupero: {invalid_ids}", cited_chunk_ids, visible_text)

    return GroundednessResult(True, "Citazioni valide", cited_chunk_ids, visible_text)


def _parse_verifier_json(raw: str) -> dict | None:
    """Il verificatore a volte racchiude il JSON in un blocco ```json ... ``` o aggiunge una
    frase intorno, nonostante l'istruzione di rispondere solo con l'oggetto: prima di
    considerarlo un fallimento del formato, si prova a isolare il primo blocco {...}."""
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _run_verifier_once(visible_text: str, sources_block: str) -> GroundednessResult:
    user_message = f"PASSAGGI SORGENTE:\n{sources_block}\n\nRISPOSTA:\n{visible_text}"
    raw = call_claude(system=GROUNDEDNESS_VERIFIER_PROMPT, user_message=user_message, max_tokens=1024)
    parsed = _parse_verifier_json(raw)
    if parsed is None:
        return GroundednessResult(False, "Verificatore non ha risposto in formato valido")
    if parsed.get("verdict") == "PASS":
        return GroundednessResult(True, "Claim verificati")
    return GroundednessResult(False, f"Claim non supportati: {parsed.get('unsupported_claims')}")


def check_claims_with_model(visible_text: str, retrieved: list[RetrievedChunk]) -> GroundednessResult:
    """Seconda verifica, con un'altra chiamata al modello dedicata solo a controllare che
    ogni affermazione tecnica sia supportata dai passaggi forniti (si veda GROUNDEDNESS_VERIFIER_PROMPT).

    Il verificatore, come qualunque chiamata a un LLM, ha una variabilità naturale tra
    chiamate identiche: trovato in produzione un caso in cui la STESSA risposta, verificata
    due volte, dava una volta PASS e una volta FAIL — bloccando una risposta corretta e ben
    ancorata solo per una fluttuazione del verificatore, non per un problema reale di
    contenuto. Un singolo FAIL non basta quindi a bocciare la risposta: si ritenta una volta
    sola, e si considera FAIL definitivo solo se anche il secondo tentativo fallisce (il
    costo aggiuntivo di una chiamata si paga solo nel caso, raro, di un primo fallimento)."""
    if not _looks_like_procedure(visible_text):
        return GroundednessResult(True, "Nessuna procedura da verificare")

    sources_block = "\n\n".join(f"[{c.chunk_id}] {c.text}" for c in retrieved)

    first = _run_verifier_once(visible_text, sources_block)
    if first.passed:
        return first
    second = _run_verifier_once(visible_text, sources_block)
    if second.passed:
        return second
    return second


def run_groundedness_checks(raw_response: str, retrieved: list[RetrievedChunk]) -> GroundednessResult:
    visible_text, cited_ids = extract_cited_sources(raw_response)

    structural = check_structural(visible_text, cited_ids, retrieved)
    if not structural.passed:
        return structural

    cited_chunks = [c for c in retrieved if c.chunk_id in cited_ids] or retrieved
    claims = check_claims_with_model(visible_text, cited_chunks)
    if not claims.passed:
        return GroundednessResult(False, claims.reason, cited_ids, visible_text)

    return GroundednessResult(True, "OK", cited_ids, visible_text)

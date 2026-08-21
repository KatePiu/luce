"""Controlli applicativi anti-allucinazione, eseguiti DOPO la generazione.

Non ci si affida solo al prompt: qui si verifica meccanicamente che la
risposta sia ancorata alle fonti recuperate, prima di mostrarla all'utente.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.integrations.anthropic_client import call_claude
from app.rag.llm_json import parse_json_response
from app.rag.prompt import GROUNDEDNESS_VERIFIER_PROMPT
from app.rag.retrieval import RetrievedChunk

CITED_SOURCES_RE = re.compile(r"<cited_sources>(.*?)</cited_sources>", re.DOTALL)
SUGGESTED_VIDEOS_RE = re.compile(r"<suggested_videos>(.*?)</suggested_videos>", re.DOTALL)


@dataclass
class GroundednessResult:
    passed: bool
    reason: str = ""
    cited_chunk_ids: list[str] | None = None
    visible_text: str = ""
    suggested_video_ids: list[str] | None = None


def _extract_id_list(raw_response: str, pattern: re.Pattern) -> list[str]:
    match = pattern.search(raw_response)
    if not match:
        return []
    try:
        ids = json.loads(match.group(1))
        if isinstance(ids, list):
            return [str(i) for i in ids]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def extract_cited_sources(raw_response: str) -> tuple[str, list[str], list[str]]:
    """Separa il testo destinato all'utente dai blocchi <cited_sources>...</cited_sources> e
    <suggested_videos>...</suggested_videos> (video indicizzati solo per titolo, proposti per
    video_id invece che con un URL scritto a mano dal modello — vedi Luce_Anteprime_Video_
    Cowork_Specifica, sezione 5)."""
    cited_ids = _extract_id_list(raw_response, CITED_SOURCES_RE)
    suggested_ids = _extract_id_list(raw_response, SUGGESTED_VIDEOS_RE)
    visible_text = CITED_SOURCES_RE.sub("", raw_response)
    visible_text = SUGGESTED_VIDEOS_RE.sub("", visible_text).strip()
    return visible_text, cited_ids, suggested_ids


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


def _run_verifier_once(visible_text: str, sources_block: str) -> GroundednessResult:
    user_message = f"PASSAGGI SORGENTE:\n{sources_block}\n\nRISPOSTA:\n{visible_text}"
    raw = call_claude(system=GROUNDEDNESS_VERIFIER_PROMPT, user_message=user_message, max_tokens=1024)
    parsed = parse_json_response(raw)
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
    visible_text, cited_ids, suggested_video_ids = extract_cited_sources(raw_response)

    structural = check_structural(visible_text, cited_ids, retrieved)
    if not structural.passed:
        return structural

    cited_chunks = [c for c in retrieved if c.chunk_id in cited_ids] or retrieved
    claims = check_claims_with_model(visible_text, cited_chunks)
    if not claims.passed:
        return GroundednessResult(False, claims.reason, cited_ids, visible_text, suggested_video_ids)

    return GroundednessResult(True, "OK", cited_ids, visible_text, suggested_video_ids)

"""Client Anthropic centralizzato. Nessuno strumento web è mai abilitato:
il modello risponde solo in base al contesto passato esplicitamente nel messaggio."""

from __future__ import annotations

import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

_client = anthropic.Anthropic(api_key=settings.anthropic_api_key) if settings.anthropic_api_key else None


def _require_client() -> anthropic.Anthropic:
    if _client is None:
        raise RuntimeError(
            "ANTHROPIC_API_KEY non configurata: impossibile generare risposte. Aggiungila al file .env."
        )
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def call_claude(system: str, user_message: str, max_tokens: int = 1500, history: list[dict] | None = None) -> str:
    client = _require_client()
    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=max_tokens,
        system=system,
        messages=messages,
        # Nessun campo "tools": il modello non ha accesso a ricerca web o altre funzioni esterne.
    )
    return "".join(block.text for block in response.content if block.type == "text")

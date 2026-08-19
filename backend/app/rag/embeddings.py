"""Wrapper per il provider di embedding (Voyage AI, consigliato da Anthropic per l'uso con Claude).

Isolato in un solo punto: per cambiare provider (es. OpenAI embeddings) basta
riscrivere `embed_texts`/`embed_query`, mantenendo la stessa dimensione del
vettore configurata in `backend/db/schema.sql` (o eseguendo una migrazione).
"""

from __future__ import annotations

import voyageai
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key) if settings.voyage_api_key else None


def _require_client() -> voyageai.Client:
    if _client is None:
        raise RuntimeError(
            "VOYAGE_API_KEY non configurata: impossibile calcolare gli embedding. "
            "Aggiungila al file .env prima di indicizzare i materiali."
        )
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embedding per contenuti da indicizzare (i chunk delle fonti)."""
    client = _require_client()
    result = client.embed(texts, model=settings.voyage_model, input_type="document")
    return result.embeddings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def embed_query(text: str) -> list[float]:
    """Embedding per la domanda dell'utente (usa input_type='query' per risultati migliori)."""
    client = _require_client()
    result = client.embed([text], model=settings.voyage_model, input_type="query")
    return result.embeddings[0]

"""Wrapper per il provider di embedding (Voyage AI, consigliato da Anthropic per l'uso con Claude).

Isolato in un solo punto: per cambiare provider (es. OpenAI embeddings) basta
riscrivere `embed_texts`/`embed_query`, mantenendo la stessa dimensione del
vettore configurata in `backend/db/schema.sql` (o eseguendo una migrazione).
"""

from __future__ import annotations

import voyageai
import voyageai.error as voyage_errors
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import settings

_client = voyageai.Client(api_key=settings.voyage_api_key) if settings.voyage_api_key else None

# Errori transitori (rete/servizio momentaneamente non disponibile): ha senso
# ritentare. Un RateLimitError NON va ritentato con un semplice backoff breve:
# sul piano gratuito senza carta di pagamento il limite è 3 richieste/minuto,
# nessun numero ragionevole di tentativi lo risolve — va segnalato subito con
# un messaggio chiaro (vedi RATE_LIMIT_MESSAGE) invece di far perdere tempo
# all'utente con un errore criptico dopo 3 tentativi falliti.
_RETRYABLE_ERRORS = (
    voyage_errors.APIConnectionError,
    voyage_errors.ServiceUnavailableError,
    voyage_errors.Timeout,
    voyage_errors.TryAgain,
)

RATE_LIMIT_MESSAGE = (
    "Limite di richieste Voyage AI superato. Se l'account non ha ancora un "
    "metodo di pagamento registrato, il piano gratuito permette solo 3 "
    "richieste al minuto: aggiungilo su dash.voyageai.com (Billing) per "
    "sbloccare il limite più alto necessario per indicizzare file con molti "
    "contenuti o per l'uso reale della chat."
)


def _require_client() -> voyageai.Client:
    if _client is None:
        raise RuntimeError(
            "VOYAGE_API_KEY non configurata: impossibile calcolare gli embedding. "
            "Aggiungila al file .env prima di indicizzare i materiali."
        )
    return _client


_BATCH_SIZE = 16  # chunk più piccoli per chiamata: meno rischio di timeout su file con molti chunk (es. 100 casi)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), retry=retry_if_exception_type(_RETRYABLE_ERRORS))
def _embed_batch(texts: list[str]) -> list[list[float]]:
    client = _require_client()
    result = client.embed(texts, model=settings.voyage_model, input_type="document")
    return result.embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embedding per contenuti da indicizzare (i chunk delle fonti), a gruppi di
    _BATCH_SIZE: un'unica chiamata con centinaia di testi rischia di superare
    il timeout della richiesta HTTP di caricamento."""
    embeddings: list[list[float]] = []
    try:
        for i in range(0, len(texts), _BATCH_SIZE):
            embeddings.extend(_embed_batch(texts[i : i + _BATCH_SIZE]))
    except voyage_errors.RateLimitError as exc:
        raise RuntimeError(RATE_LIMIT_MESSAGE) from exc
    return embeddings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8), retry=retry_if_exception_type(_RETRYABLE_ERRORS))
def _embed_query_call(text: str) -> list[float]:
    client = _require_client()
    result = client.embed([text], model=settings.voyage_model, input_type="query")
    return result.embeddings[0]


def embed_query(text: str) -> list[float]:
    """Embedding per la domanda dell'utente (usa input_type='query' per risultati migliori)."""
    try:
        return _embed_query_call(text)
    except voyage_errors.RateLimitError as exc:
        raise RuntimeError(RATE_LIMIT_MESSAGE) from exc

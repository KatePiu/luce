"""Client per le API Superchat, basato sulla documentazione ufficiale
(https://developers.superchat.com/) verificata il 19/08/2026.

Confermato dalla documentazione:
- Autenticazione: header `X-API-KEY`.
- Invio messaggi: POST /messages — {from: {channel_id}, to: [{identifier}], content: {type, ...}}.
- File: POST /files per caricare, GET /files/{id} per ottenere un link di download
  temporaneo (utile per gli allegati vocali in ingresso su WhatsApp).
- Conversazioni: PATCH /conversations/{id} — non esiste un flag esplicito "modalità bot";
  il modo documentato per togliere una conversazione dall'automazione è valorizzare
  `assigned_users` con l'id di un operatore umano.
- Rate limit: 2500 richieste / 5 minuti per workspace.
- Webhook: POST /webhooks per creare una sottoscrizione (es. evento `message_inbound`);
  la risposta include un `secret` "usato per firmare le consegne del webhook", ma la
  documentazione pubblica non specifica l'algoritmo/header esatto della firma.
  NON INVENTIAMO uno schema di verifica: `verify_webhook_signature` qui sotto è un
  punto di estensione da completare seguendo le istruzioni esatte fornite da Superchat
  (supporto/dashboard) prima del go-live. Nel frattempo la protezione principale contro
  i duplicati resta la deduplicazione per `id` evento, che *è* documentata ed è
  implementata nel webhook handler (vedi app/routers/superchat_webhook.py).
"""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


def _headers() -> dict:
    return {"X-API-KEY": settings.superchat_api_key}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def send_text_message(to_identifier: str, text: str) -> dict:
    payload = {
        "from": {"channel_id": settings.superchat_channel_id},
        "to": [{"identifier": to_identifier}],
        "content": {"type": "text", "body": text},
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{settings.superchat_api_base}/messages", headers=_headers(), json=payload)
        response.raise_for_status()
        return response.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def get_file_download_url(file_id: str) -> str:
    with httpx.Client(timeout=30) as client:
        response = client.get(f"{settings.superchat_api_base}/files/{file_id}", headers=_headers())
        response.raise_for_status()
        return response.json()["link"]["url"]


def download_file_bytes(file_id: str) -> tuple[bytes, str]:
    """Scarica l'allegato (es. audio del messaggio vocale). Ritorna (bytes, mime_type)."""
    download_url = get_file_download_url(file_id)
    with httpx.Client(timeout=60) as client:
        response = client.get(download_url)
        response.raise_for_status()
        mime_type = response.headers.get("content-type", "audio/ogg")
        return response.content, mime_type


def assign_conversation_to_human(conversation_id: str, human_user_ids: list[str]) -> dict:
    """Toglie la conversazione dall'automazione assegnandola a uno o più operatori
    (meccanismo documentato — non esiste un flag 'bot on/off' esplicito nelle API)."""
    payload = {"assigned_users": human_user_ids}
    with httpx.Client(timeout=30) as client:
        response = client.patch(
            f"{settings.superchat_api_base}/conversations/{conversation_id}", headers=_headers(), json=payload
        )
        response.raise_for_status()
        return response.json()


def create_webhook(target_url: str, events: list[str]) -> dict:
    """Da eseguire una sola volta in fase di setup (o da script di provisioning),
    non ad ogni richiesta. Ritorna anche il `secret` di firma: salvarlo in
    SUPERCHAT_WEBHOOK_SECRET."""
    payload = {"target_url": target_url, "events": [{"type": e} for e in events]}
    with httpx.Client(timeout=30) as client:
        response = client.post(f"{settings.superchat_api_base}/webhooks", headers=_headers(), json=payload)
        response.raise_for_status()
        return response.json()


def verify_webhook_signature(raw_body: bytes, headers: dict) -> bool:
    """PLACEHOLDER — da completare con lo schema di firma esatto comunicato da Superchat
    (la documentazione pubblica conferma che le consegne sono firmate con il `secret`
    restituito da create_webhook, ma non ne specifica l'header/algoritmo).
    Finché questa funzione non è completata e verificata, NON usarla come unico
    controllo di sicurezza: il webhook deve comunque essere esposto solo su HTTPS,
    con un URL non indovinabile, e la deduplicazione per id evento resta obbligatoria."""
    if not settings.superchat_webhook_secret:
        return True  # nessun segreto configurato: nessuna verifica possibile, si procede solo con la dedup per id
    raise NotImplementedError(
        "Verifica firma webhook Superchat non ancora implementata: confermare con il supporto "
        "Superchat l'header e l'algoritmo esatti prima di abilitarla in produzione."
    )

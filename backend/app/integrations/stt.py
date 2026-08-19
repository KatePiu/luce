"""Trascrizione dei messaggi vocali. Usa un endpoint compatibile con l'API OpenAI
(es. Whisper) — configurabile via STT_API_BASE/STT_API_KEY/STT_MODEL in .env."""

from __future__ import annotations

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=8))
def transcribe_audio(audio_bytes: bytes, filename: str, mime_type: str) -> str:
    if not settings.stt_api_key:
        raise RuntimeError("STT_API_KEY non configurata: impossibile trascrivere i messaggi vocali.")

    files = {"file": (filename, audio_bytes, mime_type)}
    data = {"model": settings.stt_model, "language": "it"}
    headers = {"Authorization": f"Bearer {settings.stt_api_key}"}

    with httpx.Client(timeout=60) as client:
        response = client.post(
            f"{settings.stt_api_base}/audio/transcriptions", headers=headers, files=files, data=data
        )
        response.raise_for_status()
        return response.json()["text"].strip()

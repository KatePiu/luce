"""Costruzione del link "da aprire" per un video, con deep-link al timestamp quando la
piattaforma lo supporta — Luce_Anteprime_Video_Cowork_Specifica, sezione 4. La logica dipende
solo dal campo `platform` del record video: passare da Drive a Vimeo o YouTube richiede solo
di aggiornare quel campo, non il prompt né il codice di Luce."""

from __future__ import annotations

import re
from urllib.parse import urlparse

_TIMESTAMP_RE = re.compile(r"^(?:(\d+):)?(\d+):(\d+)$")


def _timestamp_to_seconds(timestamp: str) -> int | None:
    """"mm:ss" o "hh:mm:ss" -> secondi totali. None se il formato non è riconosciuto (non si
    inventa mai un punto temporale a partire da un dato malformato)."""
    match = _TIMESTAMP_RE.match(timestamp.strip())
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    total = int(minutes) * 60 + int(seconds)
    if hours:
        total += int(hours) * 3600
    return total


def build_video_open_url(url: str, platform: str, start_timestamp: str | None) -> str:
    """URL da usare sia per l'anteprima cliccabile sia per il link testuale — sempre lo
    stesso, come richiesto dal documento. Se il timestamp non è disponibile o la piattaforma
    non supporta il deep-link (es. Google Drive), ritorna l'URL del video intero invariato:
    il timestamp resta comunque visibile in chat come testo, mostrato separatamente."""
    if not start_timestamp:
        return url
    seconds = _timestamp_to_seconds(start_timestamp)
    if seconds is None:
        return url

    if platform == "youtube":
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}t={seconds}s"
    if platform == "vimeo":
        parsed = urlparse(url)
        if parsed.fragment:
            return url
        return f"{url}#t={seconds}s"
    # Drive e altre piattaforme: nessun deep-link al timestamp supportato in modo affidabile.
    return url

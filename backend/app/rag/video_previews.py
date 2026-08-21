"""Mappatura delle anteprime video già disponibili — Luce_Anteprime_Video_Cowork_Specifica,
sezione 7. Usata una sola volta per popolare `preview_url` sui video già caricati (endpoint
`POST /admin/videos/seed-previews`), e come riferimento per nuovi video con lo stesso schema
di naming. Le chiavi sono i titoli/nomi file così come compaiono nel documento; l'URL si
costruisce dalla cartella base + il nome codificato, non è scritto a mano per i 32 elementi."""

from __future__ import annotations

import re
from urllib.parse import quote

PREVIEW_BASE_URL = "https://www.360maker.it/Luce/anteprime_video/"

_TITLES = [
    "01 - HENNE SHATUSH - INTRO",
    "01 - INFUSION - PRESENTAZIONE PRODOTTI",
    "01_color_oil",
    "02 - HENNE SHATUSH - ROSSO PROFONDO",
    "02 - INFUSION - TECNICA n°1",
    "03 - HENNE SHATUSH - ROSSO",
    "03 - INFUSION - TECNICA n°2",
    "04 - HENNE SHATUSH - CASTANO",
    "04 - INFUSION - TECNICA n°3",
    "05 - HENNE SHATUSH - BIONDO",
    "05 - INFUSION - TECNICA n°4",
    "amo",
    "coppolino",
    "HAIR MINERAL RELAX",
    "INFUSION MOUSSE REPAIR",
    "MEDITERRANEAN COMPLEX",
    "MR. COPPOLA",
    "NATURA MAGICA",
    "PHON MARIAM",
    "PHON MATILDA",
    "PHON RITA",
    "PHON SOPHIE",
    "SHATUSH COLOR TREND 20 Ottobre 2025",
    "TAGLIO MARIAM",
    "TAGLIO MATILDA",
    "TAGLIO RITA",
    "TAGLIO SOPHIE",
    "TECNICO MARIAM",
    "TECNICO SOPHIE",
    "TUTORIAL TAGLIO SOPHIE - LIVE PE 2026 CRUISE",
    "TUTORIAL TECNICO HANNA - LIVE AI 2025 RITRATTO",
    "VIDEO LINEA SHATUSH COMPLETA",
]

VIDEO_PREVIEW_MAP: dict[str, str] = {title: f"{PREVIEW_BASE_URL}{quote(title)}.png" for title in _TITLES}

_EXTENSION_RE = re.compile(r"\.(mp4|mov|mkv|avi|webm)$", re.IGNORECASE)


def _normalize(title: str) -> str:
    stripped = title.strip()
    # Alcuni titoli hanno doppia estensione nel nome (es. "NATURA MAGICA.mov.mp4"): rimuove
    # tutte le estensioni finali concatenate, non solo l'ultima.
    while True:
        new_stripped = _EXTENSION_RE.sub("", stripped)
        if new_stripped == stripped:
            break
        stripped = new_stripped
    return re.sub(r"\s+", " ", stripped).strip().lower()


_NORMALIZED_MAP = {_normalize(title): url for title, url in VIDEO_PREVIEW_MAP.items()}


def match_preview_url(video_title: str) -> str | None:
    """Trova la preview_url per un titolo video reale, tollerando estensione file
    (.mp4/.mov/...), spazi ripetuti e maiuscole/minuscole diverse. None se non trovata —
    non si inventa mai un URL di anteprima non presente nella mappatura."""
    return _NORMALIZED_MAP.get(_normalize(video_title))

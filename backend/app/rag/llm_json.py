"""Parsing tollerante di risposte JSON di un LLM.

Un modello istruito a rispondere "solo con l'oggetto JSON" a volte lo racchiude comunque in
un blocco ```json ... ``` o aggiunge una frase intorno: prima di considerarlo un fallimento
di formato, conviene provare a isolare il primo blocco {...}. Usato dal verificatore di
groundedness e dall'estrazione della scheda diagnostica.
"""

from __future__ import annotations

import json
import re


def parse_json_response(raw: str) -> dict | None:
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

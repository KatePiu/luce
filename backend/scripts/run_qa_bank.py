"""Esegue l'intera banca di domande/risposte attese contro il tutor live (via
/admin/test-response) e salva i risultati grezzi per la revisione. Script diagnostico
temporaneo, non parte dell'applicazione — non richiede dipendenze extra oltre requests."""

import json
import sys
import time

import requests

BASE = "https://luce-backend-en0z.onrender.com"
TOKEN = json.load(open("/tmp/luce_login.json"))["access_token"]
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

items = json.load(open(sys.argv[1]))
out_path = sys.argv[2]

results = []
for idx, item in enumerate(items, 1):
    q = item["question"]
    try:
        r = requests.post(f"{BASE}/admin/test-response", params={"question": q}, headers=HEADERS, timeout=60)
        resp = r.json()
    except Exception as exc:
        resp = {"error": str(exc)}

    results.append(
        {
            "id": item["id"],
            "category": item["category"],
            "question": q,
            "expected_answer": item["expected_answer"],
            "actual_text": resp.get("text"),
            "escalated": resp.get("escalated"),
            "retrieval_score": resp.get("retrieval_score"),
            "cited_sources": [c.get("title") for c in resp.get("cited_sources", [])],
        }
    )
    print(f"[{idx}/{len(items)}] id={item['id']} escalated={resp.get('escalated')} | {q[:70]}", flush=True)
    json.dump(results, open(out_path, "w"), ensure_ascii=False, indent=2)
    time.sleep(0.3)

print("DONE", len(results), "risultati salvati in", out_path)

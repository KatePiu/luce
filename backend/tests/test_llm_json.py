from app.rag.llm_json import parse_json_response


def test_parse_json_response_handles_plain_json():
    assert parse_json_response('{"verdict": "PASS", "unsupported_claims": []}') == {
        "verdict": "PASS",
        "unsupported_claims": [],
    }


def test_parse_json_response_handles_markdown_code_fence():
    # Bug reale: il verificatore a volte racchiude il JSON in ```json ... ``` nonostante
    # l'istruzione di rispondere solo con l'oggetto, facendo fallire una risposta corretta.
    raw = '```json\n{"verdict": "PASS", "unsupported_claims": []}\n```'
    assert parse_json_response(raw) == {"verdict": "PASS", "unsupported_claims": []}


def test_parse_json_response_handles_leading_prose():
    raw = 'Ecco il risultato:\n{"verdict": "FAIL", "unsupported_claims": ["tempo di posa"]}'
    assert parse_json_response(raw) == {"verdict": "FAIL", "unsupported_claims": ["tempo di posa"]}


def test_parse_json_response_returns_none_for_garbage():
    assert parse_json_response("non sono riuscito a rispondere in JSON") is None

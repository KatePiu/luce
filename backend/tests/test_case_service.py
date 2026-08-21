from app.case_service import _confidence_label, case_to_diagnostic_dict
from app.rag.case_extraction import CASE_FIELDS


class _FakeCase:
    def __init__(self, **kwargs):
        for field in CASE_FIELDS + ["fonti_trovate", "livello_confidenza"]:
            setattr(self, field, None)
        for k, v in kwargs.items():
            setattr(self, k, v)


def test_confidence_label_thresholds():
    assert _confidence_label(0.9) == "alto"
    assert _confidence_label(0.7) == "alto"
    assert _confidence_label(0.6) == "medio"
    assert _confidence_label(0.55) == "medio"
    assert _confidence_label(0.4) == "basso"
    assert _confidence_label(None) is None


def test_case_to_diagnostic_dict_returns_empty_for_none():
    assert case_to_diagnostic_dict(None) == {}


def test_case_to_diagnostic_dict_maps_fields():
    case = _FakeCase(
        problema_osservato="troppo caldo",
        area="colorazione",
        tecnica="Infusion",
        zona_coinvolta="radice",
        fonti_trovate=["Infusion_Tecnica_1_Guida_md.docx"],
        livello_confidenza="alto",
    )
    result = case_to_diagnostic_dict(case)
    assert result["problema_sintetico"] == "troppo caldo"
    assert result["tecnica"] == "Infusion"
    assert result["zona_coinvolta"] == "radice"
    assert result["fonti_trovate"] == ["Infusion_Tecnica_1_Guida_md.docx"]
    assert result["livello_confidenza"] == "alto"

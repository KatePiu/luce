from app.case_service import FEEDBACK_ESITO_MAP, FEEDBACK_STATE_MAP
from app.schemas import FEEDBACK_TYPES


def test_all_feedback_types_have_a_state_mapping():
    assert set(FEEDBACK_STATE_MAP.keys()) == set(FEEDBACK_TYPES)


def test_all_feedback_types_have_an_esito_mapping():
    assert set(FEEDBACK_ESITO_MAP.keys()) == set(FEEDBACK_TYPES)


def test_positive_outcome_moves_case_toward_validation():
    assert FEEDBACK_STATE_MAP["problema_risolto"] == "DA_VALIDARE"


def test_contacted_tutor_feedback_triggers_escalation_state():
    assert FEEDBACK_STATE_MAP["ho_dovuto_contattare_il_tutor"] == "ESCALATION_TUTOR"


def test_light_positive_signal_does_not_force_a_state_transition():
    # "Mi è stata utile" è un segnale leggero sulla risposta, non una conferma di esito
    # tecnico: non deve far avanzare da solo lo stato del caso verso la validazione.
    assert FEEDBACK_STATE_MAP["mi_e_stata_utile"] is None

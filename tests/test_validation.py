import pytest

from syncfit_ai.schema import SchemaValidationError, validate_ai_response


def valid_payload() -> dict:
    return {
        "schema_version": "1.0.0",
        "session_id": "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
        "phase_inferred": "LUTEAL",
        "fatigue_level": "MEDIUM",
        "articular_risk_pct": 40.0,
        "k_load_multiplier": 0.9,
        "alerts": ["Late luteal phase"],
        "adapted_routine": [],
    }


def test_valid_payload_parses():
    model = validate_ai_response(valid_payload())
    assert model.k_load_multiplier == 0.9
    assert model.phase_inferred == "LUTEAL"


def test_k_load_out_of_range_rejected():
    payload = valid_payload()
    payload["k_load_multiplier"] = 1.5
    with pytest.raises(SchemaValidationError):
        validate_ai_response(payload)


def test_unknown_field_rejected():
    payload = valid_payload()
    payload["surprise"] = True
    with pytest.raises(SchemaValidationError):
        validate_ai_response(payload)

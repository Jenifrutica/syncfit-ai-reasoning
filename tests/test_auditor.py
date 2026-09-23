from syncfit_ai import BiomechanicalAuditor, FakeClient
from syncfit_contracts import AIReasoningResponse

MODEL_OUTPUT = {
    "schema_version": "1.0.0",
    "phase_inferred": "LUTEAL",
    "fatigue_level": "LOW",
    "articular_risk_pct": 5.0,
    "k_load_multiplier": 1.05,
    "alerts": ["model alert"],
    "adapted_routine": [
        {
            "exercise_original": "Heavy back squat",
            "blocked": False,
            "block_reason": "",
            "exercise_substitute": "",
            "series_adapted": 5,
            "reps_adapted": 5,
            "weight_suggested_kg": 80.0,
        }
    ],
}


def test_audit_returns_validated_contract(ovulatory_request):
    auditor = BiomechanicalAuditor(FakeClient(response=MODEL_OUTPUT))
    result = auditor.audit(ovulatory_request)
    assert isinstance(result, AIReasoningResponse)
    assert result.k_load_multiplier == 0.72
    assert result.phase_inferred == "OVULATORY"
    assert result.session_id == ovulatory_request.session_id


def test_audit_enforces_rules_over_model(ovulatory_request):
    auditor = BiomechanicalAuditor(FakeClient(response=MODEL_OUTPUT))
    result = auditor.audit(ovulatory_request)
    exercises = {e.exercise_original: e for e in result.adapted_routine}
    assert exercises["Heavy back squat"].blocked is True
    assert exercises["Plyometric box jumps"].blocked is True
    assert len(result.adapted_routine) == len(ovulatory_request.programmed_routine)


def test_audit_uses_cache(ovulatory_request):
    client = FakeClient(response=MODEL_OUTPUT)
    auditor = BiomechanicalAuditor(client)
    auditor.audit(ovulatory_request)
    auditor.audit(ovulatory_request)
    assert len(client.calls) == 1
    assert auditor.cache.hits == 1


def test_audit_passes_session_id_to_client(ovulatory_request):
    client = FakeClient(response=MODEL_OUTPUT)
    BiomechanicalAuditor(client).audit(ovulatory_request)
    assert client.calls[0]["session_id"] == ovulatory_request.session_id

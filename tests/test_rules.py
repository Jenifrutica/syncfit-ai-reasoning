from syncfit_ai.rules import enforce_rules, estimate_articular_risk, evaluate_exercise
from syncfit_core.enums import InferredPhase


def test_ovulatory_blocks_high_impact(ovulatory_request):
    core = ovulatory_request.core_result
    blocked, reason, substitute = evaluate_exercise("Heavy back squat", core, 14)
    assert blocked is True
    assert "ACL" in reason
    assert substitute


def test_ovulatory_does_not_block_bench_press_in_cycle(ovulatory_request):
    core = ovulatory_request.core_result
    blocked, _, _ = evaluate_exercise("Flat barbell bench press", core, 14)
    assert blocked is False


def test_gestational_week_16_blocks_supine(gestational_request):
    core = gestational_request.core_result
    blocked, reason, substitute = evaluate_exercise("Flat barbell bench press", core, 18)
    assert blocked is True
    assert "supine" in reason.lower() or "venous" in reason.lower()
    assert "Incline" in substitute


def test_gestational_does_not_block_squat_in_trimester_2(gestational_request):
    core = gestational_request.core_result
    blocked, _, _ = evaluate_exercise("Heavy back squat", core, 18)
    assert blocked is False


def test_incline_bench_is_not_supine(gestational_request):
    core = gestational_request.core_result
    blocked, _, _ = evaluate_exercise("Incline bench press (30 degrees)", core, 18)
    assert blocked is False


def test_enforce_preserves_k_load_and_phase(ovulatory_request):
    payload = {
        "schema_version": "0.0.0",
        "phase_inferred": "LUTEAL",
        "fatigue_level": "LOW",
        "k_load_multiplier": 1.05,
        "articular_risk_pct": 10.0,
        "alerts": [],
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
    result = enforce_rules(ovulatory_request.core_result, payload, ovulatory_request)
    assert result["k_load_multiplier"] == 0.72
    assert result["phase_inferred"] == "OVULATORY"
    assert result["fatigue_level"] == "HIGH"
    assert result["session_id"] == ovulatory_request.session_id


def test_enforce_blocks_and_reduces(ovulatory_request):
    payload = {"k_load_multiplier": 1.0, "adapted_routine": []}
    result = enforce_rules(ovulatory_request.core_result, payload, ovulatory_request)
    exercises = {e["exercise_original"]: e for e in result["adapted_routine"]}
    squat = exercises["Heavy back squat"]
    assert squat["blocked"] is True
    assert squat["series_adapted"] <= 3
    assert squat["weight_suggested_kg"] < 80.0
    assert exercises["Plyometric box jumps"]["blocked"] is True
    assert len(result["adapted_routine"]) == len(ovulatory_request.programmed_routine)


def test_estimate_articular_risk_bounds(ovulatory_request):
    risk = estimate_articular_risk(ovulatory_request.core_result)
    assert 0.0 <= risk <= 100.0
    assert risk > 30.0  # ovulatory adds 30


def test_estimate_fills_missing_risk(ovulatory_request):
    payload = {"k_load_multiplier": 0.72, "adapted_routine": []}
    result = enforce_rules(ovulatory_request.core_result, payload, ovulatory_request)
    assert "articular_risk_pct" in result
    assert result["articular_risk_pct"] > 0

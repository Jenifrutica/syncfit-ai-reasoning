import json

from syncfit_ai import FakeClient, RoutinePlanner, build_offline_routine, enrich_routine
from syncfit_contracts import RoutineRequest, RoutineResponse, exercises_for_groups
from syncfit_core import EngineResult
from syncfit_core.enums import FatigueLevel, InferredPhase, Modality
from syncfit_core.features import build_feature_vector


def make_core_result(phase: InferredPhase, modality=Modality.MENSTRUAL_CYCLE, day=14, k_load=0.72):
    features = build_feature_vector(modality, day, 0.42, 28.5, 12.8)
    return EngineResult(
        phase_inferred=phase,
        fatigue_probability=0.6,
        fatigue_level=FatigueLevel.MEDIUM,
        k_load=k_load,
        rmssd_hrv_ms=28.5,
        features=features,
    )


def request(groups, language="EN", per_group=2):
    return RoutineRequest(muscle_groups=groups, language=language, exercises_per_group=per_group)


def model_output(*exercise_ids):
    return {
        "schema_version": "1.1.0",
        "language": "EN",
        "muscle_groups": ["GLUTES"],
        "alerts": [],
        "routine": [
            {
                "exercise_id": eid,
                "series_adapted": 3,
                "reps_adapted": 10,
                "weight_suggested_kg": 0.0,
            }
            for eid in exercise_ids
        ],
    }


def test_offline_routine_is_valid_and_low_impact_in_ovulatory():
    core = make_core_result(InferredPhase.OVULATORY)
    result = RoutineResponse.model_validate(build_offline_routine(request(["FULL_LEG"]), core))
    assert result.phase_inferred == "OVULATORY"
    assert all(entry.impact == "LOW" for entry in result.routine)
    assert all(entry.image_url for entry in result.routine)


def test_planner_blocks_high_impact_and_substitutes():
    core = make_core_result(InferredPhase.OVULATORY)
    planner = RoutinePlanner(FakeClient(response=model_output("back-squat", "goblet-squat")))
    result = planner.plan(request(["QUADRICEPS"]), core)
    entries = {e.exercise_id: e for e in result.routine}
    assert entries["back-squat"].blocked is True
    assert entries["back-squat"].exercise_substitute
    assert entries["goblet-squat"].blocked is False


def test_planner_blocks_supine_in_gestational_week_16():
    core = make_core_result(InferredPhase.TRIMESTER_2, modality=Modality.GESTATIONAL, day=18, k_load=0.85)
    planner = RoutinePlanner(FakeClient(response=model_output("flat-bench-press")))
    result = planner.plan(request(["CHEST"]), core)
    entry = result.routine[0]
    assert entry.blocked is True
    assert entry.impact == "MEDIUM"


def test_planner_completes_missing_groups():
    core = make_core_result(InferredPhase.FOLLICULAR, k_load=0.95)
    # Model only returns a GLUTES exercise, but QUADRICEPS was requested too.
    planner = RoutinePlanner(FakeClient(response=model_output("hip-thrust")))
    result = planner.plan(request(["GLUTES", "QUADRICEPS"]), core)
    groups = {str(g) for entry in result.routine for g in entry.muscle_groups}
    assert "GLUTES" in groups and "QUADRICEPS" in groups


def test_planner_ignores_unknown_ids_and_falls_back():
    core = make_core_result(InferredPhase.FOLLICULAR, k_load=0.95)
    planner = RoutinePlanner(FakeClient(response=model_output("not-a-real-id")))
    result = planner.plan(request(["ABS"]), core)
    assert len(result.routine) >= 1
    assert all(entry.exercise_id for entry in result.routine)


def test_localized_output_in_spanish():
    core = make_core_result(InferredPhase.FOLLICULAR, k_load=0.95)
    planner = RoutinePlanner(FakeClient(response=model_output("goblet-squat")))
    result = planner.plan(request(["QUADRICEPS"], language="ES"), core)
    assert result.language == "ES"
    assert result.routine[0].description.es


def test_planner_uses_cache():
    core = make_core_result(InferredPhase.FOLLICULAR, k_load=0.95)
    client = FakeClient(response=model_output("goblet-squat"))
    planner = RoutinePlanner(client)
    planner.plan(request(["QUADRICEPS"]), core)
    planner.plan(request(["QUADRICEPS"]), core)
    assert len(client.calls) == 1


def test_enrich_routine_returns_contract_payload():
    core = make_core_result(InferredPhase.FOLLICULAR, k_load=0.95)
    req = request(["QUADRICEPS"])
    catalog = exercises_for_groups(["QUADRICEPS"])
    payload = enrich_routine(req, core, model_output("goblet-squat"), catalog)
    assert RoutineResponse.model_validate(payload)
    json.dumps(payload)  # serializable

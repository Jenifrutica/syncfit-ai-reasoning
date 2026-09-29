from syncfit_ai import (
    estimate_variation_pct,
    load_multiplier,
    recommend_supplements,
    suggested_weight,
)
from syncfit_ai.loads import apply_baseline_loads, baseline_for
from syncfit_ai.routine import (
    DEFAULT_EXERCISES_COUNT,
    RoutinePlanner,
    build_offline_routine,
    enrich_routine,
)
from syncfit_ai import FakeClient
from syncfit_contracts import (
    ExerciseLoad,
    RoutineRequest,
    RoutineResponse,
    SupplementAdvice,
    SupplementRequest,
)
from syncfit_core import EngineResult
from syncfit_core.enums import FatigueLevel, InferredPhase, Modality
from syncfit_core.features import build_feature_vector


def make_core_result(phase=InferredPhase.FOLLICULAR, k_load=0.9):
    features = build_feature_vector(Modality.MENSTRUAL_CYCLE, 10, 0.2, 40.0, 5.0)
    return EngineResult(
        phase_inferred=phase,
        fatigue_probability=0.4,
        fatigue_level=FatigueLevel.MEDIUM,
        k_load=k_load,
        rmssd_hrv_ms=40.0,
        features=features,
    )


def test_offline_routine_has_warmup_and_timing():
    request = RoutineRequest(muscle_groups=["GLUTES", "QUADRICEPS"], language="ES")
    payload = build_offline_routine(request, make_core_result())
    model = RoutineResponse.model_validate(payload)
    assert model.warmup
    assert model.total_estimated_minutes and model.total_estimated_minutes > 0
    assert len(model.routine) <= DEFAULT_EXERCISES_COUNT
    assert any(s.type == "EFFECTIVE" for s in model.routine[0].sets)


def test_time_budget_limits_duration():
    request = RoutineRequest(
        muscle_groups=["UPPER_BODY"], language="EN", exercises_count=6, time_budget_minutes=20
    )
    model = RoutineResponse.model_validate(build_offline_routine(request, make_core_result()))
    assert model.total_estimated_minutes <= 20


def test_load_variation_and_baseline():
    core = make_core_result(k_load=0.9)
    assert load_multiplier(core, "ENERGY") == 0.9
    assert load_multiplier(core, "NO_ENERGY") < 0.9
    assert estimate_variation_pct(core, "ENERGY") == -10.0
    assert suggested_weight(100.0, core, "MODERATE") == 85.5

    loads = [ExerciseLoad(exercise_id="goblet-squat", weight_kg=20)]
    assert baseline_for(loads, "goblet-squat") == 20.0
    entries = apply_baseline_loads(
        [{"exercise_id": "goblet-squat", "weight_suggested_kg": 0.0}], loads, core, "ENERGY"
    )
    assert entries[0]["weight_suggested_kg"] == 18.0


def test_planner_offline_applies_loads():
    core = make_core_result(k_load=0.9)
    request = RoutineRequest(muscle_groups=["QUADRICEPS"], language="EN")
    planner = RoutinePlanner(FakeClient(response={}))
    base = planner.plan_offline(request, core)
    first_id = base.routine[0].exercise_id
    loads = [ExerciseLoad(exercise_id=first_id, weight_kg=20)]
    result = planner.plan_offline(request, core, baseline_loads=loads)
    entry = next((e for e in result.routine if e.exercise_id == first_id), None)
    assert entry is not None and entry.weight_suggested_kg == 18.0


def test_supplements_pregnancy_safety():
    request = SupplementRequest(modality="GESTATIONAL", language="ES", objective="GESTATIONAL_HEALTH")
    advice = recommend_supplements(request)
    assert isinstance(advice, SupplementAdvice)
    ids = {item.supplement_id for item in advice.items}
    assert "folate" in ids
    assert "creatine" not in ids  # AVOID in pregnancy

    general = recommend_supplements(SupplementRequest(modality="MENSTRUAL_CYCLE", language="EN"))
    general_ids = {item.supplement_id for item in general.items}
    assert "creatine" in general_ids

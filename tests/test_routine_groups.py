from syncfit_contracts import RoutineRequest, get_exercise
from syncfit_ai.routine import build_prescription, enforce_prescription


def groups_of(entry: dict) -> list[str]:
    exercise = get_exercise(entry.get("exercise_id"))
    return list(exercise.muscle_groups) if exercise else []


def test_single_group_routine_only_targets_that_group():
    request = RoutineRequest(muscle_groups=["QUADRICEPS"], language="ES", exercises_count=5)
    payload = build_prescription(request)

    assert payload["routine"], "the group must keep at least one exercise"
    patterns = [entry.get("movement_pattern") for entry in payload["routine"]]
    assert len(patterns) == len(set(patterns)), patterns
    for entry in payload["routine"]:
        groups = groups_of(entry)
        assert "QUADRICEPS" in groups, (entry["exercise_original"], groups)
        assert "FULL_BODY" not in groups, (entry["exercise_original"], groups)


def test_repair_drops_exercises_outside_the_requested_group():
    request = RoutineRequest(muscle_groups=["QUADRICEPS"], language="ES", exercises_count=5)
    skeleton = build_prescription(request)

    model = {
        "routine": [
            {"exercise_id": "lat-pulldown", "movement_pattern": "pull_vertical", "series": 3, "reps": 10},
            {"exercise_id": "hip-thrust", "movement_pattern": "hip_thrust", "series": 3, "reps": 10},
            {"exercise_id": "leg-extension", "movement_pattern": "leg_extension", "series": 3, "reps": 12},
            {"exercise_id": "back-squat", "movement_pattern": "squat", "series": 4, "reps": 8},
        ]
    }
    fixed = enforce_prescription(request, None, model, skeleton)

    ids = [entry.get("exercise_id") for entry in fixed["routine"]]
    assert "lat-pulldown" not in ids
    assert "hip-thrust" not in ids
    assert len(ids) == len(set(ids))
    assert len(ids) >= 1
    for entry in fixed["routine"]:
        assert "QUADRICEPS" in groups_of(entry), entry["exercise_original"]


def test_multi_group_routine_uses_only_selected_groups():
    request = RoutineRequest(muscle_groups=["QUADRICEPS", "GLUTES"], language="ES", exercises_count=4)
    payload = build_prescription(request)

    wanted = {"QUADRICEPS", "GLUTES"}
    for entry in payload["routine"]:
        assert wanted & set(groups_of(entry)), (entry["exercise_original"], groups_of(entry))


def test_thruster_is_not_a_quad_focused_exercise():
    request = RoutineRequest(muscle_groups=["QUADRICEPS"], language="ES", exercises_count=5)
    payload = build_prescription(request)
    ids = [entry.get("exercise_id") for entry in payload["routine"]]
    assert "db-thruster" not in ids

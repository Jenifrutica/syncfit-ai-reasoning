"""Integration: simulated telemetry -> core -> reasoning.

Skipped automatically when the simulator is not installed.
"""

from __future__ import annotations

import pytest

pytest.importorskip("syncfit_simulator")

from syncfit_ai import AuditRequest, BiomechanicalAuditor, FakeClient, ProgrammedExercise
from syncfit_core import train_default_model
from syncfit_simulator import generate_session, get_scenario, run_frames

SESSION_ID = "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"

ROUTINE = [
    ProgrammedExercise("Heavy back squat", series=4, reps=6, weight_kg=80.0),
    ProgrammedExercise("Plyometric box jumps", series=3, reps=8, weight_kg=0.0),
]

# Deliberately wrong model output; the rule engine must correct it.
MODEL_OUTPUT = {
    "schema_version": "1.0.0",
    "phase_inferred": "LUTEAL",
    "fatigue_level": "LOW",
    "articular_risk_pct": 5.0,
    "k_load_multiplier": 1.05,
    "alerts": [],
    "adapted_routine": [],
}


@pytest.fixture(scope="module")
def model():
    return train_default_model(n_samples=600, seed=42)


def test_simulated_session_runs_through_core_and_reasoning(model):
    frames = generate_session(get_scenario("high_risk"), session_id=SESSION_ID, frames=2)
    core_result = run_frames(frames, model=model).final
    assert core_result.phase_inferred.value == "OVULATORY"

    request = AuditRequest(
        session_id=SESSION_ID,
        core_result=core_result,
        programmed_routine=list(ROUTINE),
    )
    result = BiomechanicalAuditor(FakeClient(response=MODEL_OUTPUT)).audit(request)

    # Deterministic values come from core, not from the model.
    assert result.phase_inferred == "OVULATORY"
    assert result.k_load_multiplier == core_result.k_load
    exercises = {e.exercise_original: e for e in result.adapted_routine}
    assert exercises["Heavy back squat"].blocked is True
    assert exercises["Plyometric box jumps"].blocked is True


def test_gestational_simulation_blocks_supine(model):
    frames = generate_session(get_scenario("gestational_t2"), session_id=SESSION_ID, frames=1)
    core_result = run_frames(frames, model=model).final
    assert core_result.phase_inferred.value == "TRIMESTER_2"

    request = AuditRequest(
        session_id=SESSION_ID,
        core_result=core_result,
        programmed_routine=[ProgrammedExercise("Flat barbell bench press", 4, 8, 45.0)],
    )
    result = BiomechanicalAuditor(FakeClient(response=MODEL_OUTPUT)).audit(request)
    assert result.adapted_routine[0].blocked is True

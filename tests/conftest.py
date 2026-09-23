import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from syncfit_ai import AuditRequest, ProgrammedExercise  # noqa: E402
from syncfit_core import EngineResult  # noqa: E402
from syncfit_core.enums import FatigueLevel, InferredPhase, Modality  # noqa: E402
from syncfit_core.features import build_feature_vector  # noqa: E402

SESSION_ID = "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"

ROUTINE = [
    ProgrammedExercise("Heavy back squat", series=4, reps=6, weight_kg=80.0),
    ProgrammedExercise("Plyometric box jumps", series=3, reps=8, weight_kg=0.0),
    ProgrammedExercise("Flat barbell bench press", series=4, reps=8, weight_kg=45.0),
]


def make_core_result(
    modality: Modality = Modality.MENSTRUAL_CYCLE,
    day_or_week: int = 14,
    phase: InferredPhase = InferredPhase.OVULATORY,
    fatigue: FatigueLevel = FatigueLevel.HIGH,
    k_load: float = 0.72,
    probability: float = 0.8,
) -> EngineResult:
    features = build_feature_vector(
        modality=modality,
        day_or_week=day_or_week,
        delta_temperature_c=0.42,
        rmssd_hrv_ms=28.5,
        isometric_force_loss_pct=12.8,
    )
    return EngineResult(
        phase_inferred=phase,
        fatigue_probability=probability,
        fatigue_level=fatigue,
        k_load=k_load,
        rmssd_hrv_ms=28.5,
        features=features,
    )


@pytest.fixture
def ovulatory_request() -> AuditRequest:
    return AuditRequest(
        session_id=SESSION_ID,
        core_result=make_core_result(),
        programmed_routine=list(ROUTINE),
    )


@pytest.fixture
def gestational_request() -> AuditRequest:
    return AuditRequest(
        session_id=SESSION_ID,
        core_result=make_core_result(
            modality=Modality.GESTATIONAL,
            day_or_week=18,
            phase=InferredPhase.TRIMESTER_2,
            fatigue=FatigueLevel.MEDIUM,
            k_load=0.85,
            probability=0.5,
        ),
        programmed_routine=list(ROUTINE),
    )

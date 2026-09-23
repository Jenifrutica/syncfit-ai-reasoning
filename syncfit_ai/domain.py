"""Domain types for a reasoning (audit) request.

The request couples the deterministic output of `syncfit-core` (phase, fatigue
level and the `k_load` multiplier) with the programmed routine to be audited.
"""

from __future__ import annotations

from dataclasses import dataclass

from syncfit_core import EngineResult


@dataclass(frozen=True)
class ProgrammedExercise:
    """A single exercise in the routine programmed before the audit."""

    exercise: str
    series: int
    reps: int
    weight_kg: float

    def as_dict(self) -> dict[str, object]:
        return {
            "exercise": self.exercise,
            "series": self.series,
            "reps": self.reps,
            "weight_kg": self.weight_kg,
        }


@dataclass(frozen=True)
class AuditRequest:
    """Everything the reasoning kernel needs for one audit."""

    session_id: str
    core_result: EngineResult
    programmed_routine: list[ProgrammedExercise]

    @property
    def day_or_week(self) -> int:
        return self.core_result.features.day_or_week

    @property
    def modality(self) -> str:
        return self.core_result.features.modality.value


__all__ = ["ProgrammedExercise", "AuditRequest"]

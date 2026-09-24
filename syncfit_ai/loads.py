"""Estimate how much the athlete's usual loads should vary.

Combines the deterministic `k_load` from `syncfit-core` with the subjective
energy check-in to adjust each exercise's baseline weight. The result is a
percentage variation plus the suggested working weight.
"""

from __future__ import annotations

from typing import Iterable

from syncfit_contracts import EnergyLevel, ExerciseLoad
from syncfit_core import EngineResult

_ENERGY_FACTOR = {
    "ENERGY": 1.00,
    "MODERATE": 0.95,
    "NO_ENERGY": 0.88,
}


def _value(item: object) -> str:
    return item.value if hasattr(item, "value") else str(item)


def baseline_for(loads: Iterable[ExerciseLoad], exercise_id: str) -> float | None:
    for load in loads:
        if load.exercise_id == exercise_id:
            return float(load.weight_kg)
    return None


def load_multiplier(
    core_result: EngineResult | None,
    energy_level: EnergyLevel | str | None = None,
) -> float:
    """Multiplier applied to the athlete's baseline weights."""
    k_load = float(core_result.k_load) if core_result is not None else 1.0
    energy = _ENERGY_FACTOR.get(_value(energy_level), 1.0) if energy_level else 1.0
    return round(k_load * energy, 3)


def estimate_variation_pct(
    core_result: EngineResult | None,
    energy_level: EnergyLevel | str | None = None,
) -> float:
    """How much the weights should vary versus the normal loads, in percent."""
    return round((load_multiplier(core_result, energy_level) - 1.0) * 100.0, 1)


def suggested_weight(
    base_weight: float,
    core_result: EngineResult | None,
    energy_level: EnergyLevel | str | None = None,
) -> float:
    """Suggested working weight from a baseline load."""
    return round(max(base_weight, 0.0) * load_multiplier(core_result, energy_level), 1)


def apply_baseline_loads(
    entries: list[dict],
    loads: Iterable[ExerciseLoad],
    core_result: EngineResult | None,
    energy_level: EnergyLevel | str | None = None,
) -> list[dict]:
    """Set `weight_suggested_kg` on each entry from the athlete's baseline loads."""
    adjusted: list[dict] = []
    for entry in entries:
        exercise_id = entry.get("exercise_id")
        item = dict(entry)
        if exercise_id:
            base = baseline_for(loads, exercise_id)
            if base is not None:
                item["weight_suggested_kg"] = suggested_weight(base, core_result, energy_level)
        adjusted.append(item)
    return adjusted


__all__ = [
    "baseline_for",
    "load_multiplier",
    "estimate_variation_pct",
    "suggested_weight",
    "apply_baseline_loads",
]

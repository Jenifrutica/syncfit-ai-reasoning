"""Deterministic biomechanical rule engine.

This is the safety net that does not depend on the language model. It guarantees
that:
  * the phase, fatigue level and `k_load` come from `syncfit-core` and are never
    altered by the model;
  * high-impact / high joint-risk exercises are blocked in the ovulatory phase
    and advanced pregnancy;
  * supine exercises are blocked from gestational week 16 onward;
  * every programmed exercise appears in the adapted routine.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from syncfit_core import EngineResult
from syncfit_core.enums import InferredPhase

from ..domain import AuditRequest

HIGH_IMPACT_KEYWORDS = (
    "squat",
    "sentadilla",
    "jump",
    "plyometric",
    "pliometr",
    "box jump",
    "clean",
    "snatch",
    "burpee",
    "sprint",
)
SUPINE_KEYWORDS = ("supine", "decubito", "decúbito", "lying", "flat bench")

SUBSTITUTES = {
    "squat": "Controlled goblet squat on a stable box",
    "sentadilla": "Sentadilla guiada con mancuerna en cajón estable",
    "jump": "Controlled step-ups",
    "plyometric": "Controlled step-ups",
    "pliometr": "Step-ups controlados",
    "default": "Guided low-impact variant",
}


def _matches(name: str, keywords: tuple[str, ...]) -> bool:
    lowered = name.lower()
    return any(keyword in lowered for keyword in keywords)


def _substitute_for(name: str) -> str:
    lowered = name.lower()
    for keyword, substitute in SUBSTITUTES.items():
        if keyword != "default" and keyword in lowered:
            return substitute
    return SUBSTITUTES["default"]


def _is_supine(name: str) -> bool:
    lowered = name.lower()
    if "incline" in lowered or "inclinad" in lowered:
        return False
    return _matches(name, SUPINE_KEYWORDS) or "bench press" in lowered


def evaluate_exercise(
    name: str,
    core_result: EngineResult,
    day_or_week: int,
) -> tuple[bool, str, str]:
    """Return `(blocked, reason, substitute)` for one exercise."""
    phase = core_result.phase_inferred

    if phase is InferredPhase.OVULATORY and _matches(name, HIGH_IMPACT_KEYWORDS):
        return (
            True,
            "Ovulatory phase: elevated ligament laxity increases ACL and tendon injury risk.",
            _substitute_for(name),
        )

    if phase is InferredPhase.TRIMESTER_3 and _matches(name, HIGH_IMPACT_KEYWORDS):
        return (
            True,
            "Advanced pregnancy: high-impact loading is contraindicated.",
            _substitute_for(name),
        )

    if core_result.features.modality.value == "GESTATIONAL" and day_or_week >= 16 and _is_supine(name):
        return (
            True,
            "Gestational week >= 16: prolonged supine decubitus compromises venous return.",
            "Incline bench press (30 degrees)",
        )

    return (False, "", "")


def estimate_articular_risk(core_result: EngineResult) -> float:
    """Deterministic articular-risk estimate used when the model omits it."""
    phase = core_result.phase_inferred
    risk = core_result.fatigue_probability * 60.0
    if phase is InferredPhase.OVULATORY:
        risk += 30.0
    elif phase is InferredPhase.TRIMESTER_3:
        risk += 25.0
    elif phase is InferredPhase.TRIMESTER_2:
        risk += 15.0
    return round(min(max(risk, 0.0), 100.0), 2)


def _adapt_exercise(
    name: str,
    series: int,
    reps: int,
    weight: float,
    core_result: EngineResult,
    day_or_week: int,
) -> dict[str, Any]:
    blocked, reason, substitute = evaluate_exercise(name, core_result, day_or_week)
    if blocked:
        return {
            "exercise_original": name,
            "blocked": True,
            "block_reason": reason,
            "exercise_substitute": substitute,
            "series_adapted": min(int(series), 3),
            "reps_adapted": max(int(reps), 10),
            "weight_suggested_kg": round(max(float(weight) * 0.6, 0.0), 1),
        }
    return {
        "exercise_original": name,
        "blocked": False,
        "block_reason": "",
        "exercise_substitute": "",
        "series_adapted": int(series),
        "reps_adapted": int(reps),
        "weight_suggested_kg": float(weight),
    }


def enforce_rules(
    core_result: EngineResult,
    payload: dict[str, Any],
    request: AuditRequest,
) -> dict[str, Any]:
    """Return a corrected copy of the model output that obeys every hard rule."""
    data = deepcopy(payload)
    day_or_week = core_result.features.day_or_week

    data["schema_version"] = "1.0.0"
    data["session_id"] = request.session_id
    data["phase_inferred"] = core_result.phase_inferred.value
    data["fatigue_level"] = core_result.fatigue_level.value
    data["k_load_multiplier"] = core_result.k_load
    data.setdefault("alerts", [])
    if not data.get("articular_risk_pct"):
        data["articular_risk_pct"] = estimate_articular_risk(core_result)

    existing = {
        item.get("exercise_original"): item
        for item in data.get("adapted_routine", [])
        if isinstance(item, dict)
    }

    adapted: list[dict[str, Any]] = []
    for exercise in request.programmed_routine:
        item = existing.get(exercise.exercise)
        if item is None:
            adapted.append(
                _adapt_exercise(
                    exercise.exercise,
                    exercise.series,
                    exercise.reps,
                    exercise.weight_kg,
                    core_result,
                    day_or_week,
                )
            )
            continue

        blocked, reason, substitute = evaluate_exercise(
            exercise.exercise, core_result, day_or_week
        )
        if blocked:
            item["blocked"] = True
            item["block_reason"] = reason
            if not item.get("exercise_substitute"):
                item["exercise_substitute"] = substitute
            item["series_adapted"] = min(int(item.get("series_adapted", exercise.series)), 3)
            item["reps_adapted"] = max(int(item.get("reps_adapted", exercise.reps)), 10)
            item["weight_suggested_kg"] = round(
                max(float(item.get("weight_suggested_kg", exercise.weight_kg)) * 0.6, 0.0), 1
            )
        else:
            item["blocked"] = False
            item["block_reason"] = ""
            item["exercise_substitute"] = ""
            item["series_adapted"] = int(item.get("series_adapted", exercise.series))
            item["reps_adapted"] = int(item.get("reps_adapted", exercise.reps))
            item["weight_suggested_kg"] = float(
                item.get("weight_suggested_kg", exercise.weight_kg)
            )
        adapted.append(item)

    data["adapted_routine"] = adapted
    return data


__all__ = [
    "HIGH_IMPACT_KEYWORDS",
    "SUPINE_KEYWORDS",
    "evaluate_exercise",
    "estimate_articular_risk",
    "enforce_rules",
]

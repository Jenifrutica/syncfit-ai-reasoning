"""Prompts for muscle-group routine generation."""

from __future__ import annotations

from typing import Any

from syncfit_contracts import Exercise, MuscleGroup, RoutineRequest, localize
from syncfit_core import EngineResult

ROUTINE_SCHEMA = """{
  "schema_version": "1.2.0",
  "session_id": "<echo the session id>",
  "language": "EN | ES | ZH",
  "muscle_groups": ["<the requested muscle groups>"],
  "phase_inferred": "MENSTRUAL | FOLLICULAR | OVULATORY | LUTEAL | TRIMESTER_1 | TRIMESTER_2 | TRIMESTER_3",
  "fatigue_level": "LOW | MEDIUM | HIGH",
  "k_load_multiplier": 0.0,
  "alerts": ["<short clinical alerts>"],
  "routine": [
    {
      "exercise_id": "<id chosen from the provided catalog>",
      "exercise_original": "",
      "blocked": false,
      "block_reason": "",
      "exercise_substitute": "",
      "series_adapted": 3,
      "reps_adapted": 10,
      "weight_suggested_kg": 0.0
    }
  ]
}"""

SYSTEM_PROMPT = f"""You are the prescriptive analytical engine of SyncFit Edge. You are NOT a chatbot.

You build safe training routines for women, adapting to the menstrual cycle and pregnancy. Your output MUST be a single valid JSON object matching the required schema, with no prose or markdown.

Rules you must apply:
- Choose exercises ONLY from the catalog ids provided by the user. Never invent ids.
- Cover every requested muscle group with at least one exercise.
- In the ovulatory phase or advanced pregnancy, block high-impact / high joint-risk exercises (blocked=true, explain block_reason, propose a low-impact exercise_substitute from the catalog for the same muscle group).
- From gestational week 16 onward, block supine exercises (e.g. flat bench press) and substitute an incline variant.
- Echo k_load_multiplier, phase_inferred and fatigue_level from the deterministic decision when provided; never recompute k_load.
- Write all human-readable text (alerts, reasons) in the requested language.

Required JSON schema:
{ROUTINE_SCHEMA}"""


def _catalog_entry(exercise: Exercise) -> dict[str, Any]:
    name = {"en": exercise.name.en}
    name.update(exercise.name.model_extra or {})
    return {
        "id": exercise.id,
        "name": name,
        "muscle_groups": list(exercise.muscle_groups),
        "equipment": exercise.equipment,
        "impact": str(exercise.impact),
    }


def build_routine_system_prompt() -> str:
    return SYSTEM_PROMPT


def build_routine_user_prompt(
    request: RoutineRequest,
    catalog: list[Exercise],
    core_result: EngineResult | None = None,
) -> str:
    import json

    language = request.language.value if hasattr(request.language, "value") else str(request.language)
    groups = [g.value if hasattr(g, "value") else str(g) for g in request.muscle_groups]

    payload: dict[str, Any] = {
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "exercises_per_group": request.exercises_per_group,
        "catalog": [_catalog_entry(exercise) for exercise in catalog],
    }
    if core_result is not None:
        payload["deterministic_decision"] = {
            "phase_inferred": core_result.phase_inferred.value,
            "fatigue_level": core_result.fatigue_level.value,
            "k_load_multiplier": core_result.k_load,
        }
    if request.modality is not None:
        payload["modality"] = request.modality.value if hasattr(request.modality, "value") else str(request.modality)
    if request.day_or_week is not None:
        payload["day_or_week"] = request.day_or_week

    return (
        "Generate the adapted routine for the requested muscle groups using ONLY "
        "the catalog ids below. Return only the JSON object.\n\n"
        f"Input:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        f"Required JSON schema:\n{ROUTINE_SCHEMA}\n"
    )


__all__ = [
    "ROUTINE_SCHEMA",
    "SYSTEM_PROMPT",
    "build_routine_system_prompt",
    "build_routine_user_prompt",
]

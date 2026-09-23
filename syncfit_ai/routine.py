"""Routine planning: muscle-group routines with deterministic safety.

The model picks exercise ids from the shared catalog; this module enriches the
output (localized name/description/image), enforces the biomechanical safety
rules and validates against `syncfit-contracts`. When the model omits groups or
entries, a deterministic catalog fallback completes the routine.
"""

from __future__ import annotations

import json
from typing import Any

from syncfit_contracts import (
    Exercise,
    RoutineRequest,
    RoutineResponse,
    exercises_for_groups,
    get_exercise,
    localize,
)
from syncfit_core import EngineResult
from syncfit_core.enums import InferredPhase

from .client import ReasoningClient
from .prompts import build_routine_system_prompt, build_routine_user_prompt
from .structures import LRUCache

_IMPACT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
DEFAULT_EXERCISES_PER_GROUP = 2

_REASONS = {
    "impact": {
        "en": "High-impact exercise blocked in this phase.",
        "es": "Ejercicio de alto impacto bloqueado en esta fase.",
        "zh": "该阶段禁用高冲击动作。",
    },
    "supine": {
        "en": "Supine exercise blocked from gestational week 16 (supine decubitus).",
        "es": "Ejercicio en supino bloqueado desde la semana 16 (decúbito supino).",
        "zh": "孕16周起禁用仰卧动作。",
    },
}
_ALERT_BLOCK = {
    "en": "Unsafe exercises were blocked by the biomechanical safety rules.",
    "es": "Se bloquearon ejercicios de riesgo por las reglas biomecánicas.",
    "zh": "已按生物力学安全规则屏蔽高风险动作。",
}


def _value(item: object) -> str:
    return item.value if hasattr(item, "value") else str(item)


def _rank(impact: object) -> int:
    return _IMPACT_RANK.get(_value(impact), 2)


def _reason(kind: str, language: str) -> str:
    table = _REASONS[kind]
    return table.get(language.lower(), table["en"])


def _max_impact(core_result: EngineResult | None) -> str:
    if core_result is None:
        return "HIGH"
    if core_result.phase_inferred in (InferredPhase.OVULATORY, InferredPhase.TRIMESTER_3):
        return "LOW"
    return "HIGH"


def _is_supine(exercise: Exercise) -> bool:
    name = exercise.name.en.lower()
    if "incline" in name:
        return False
    return "bench press" in name or "supine" in name


def _localized(exercise: Exercise, language: str) -> dict[str, str]:
    data = {"en": exercise.name.en}
    data.update(exercise.name.model_extra or {})
    description = {"en": exercise.description.en}
    description.update(exercise.description.model_extra or {})
    return {
        "name": localize(exercise.name, language),
        "description_en": description["en"],
        "description": description,
    }


def _substitute_for(
    exercise: Exercise,
    requested_groups: list[str],
    max_impact: str,
) -> Exercise | None:
    target_groups = {_value(g) for g in exercise.muscle_groups}
    for candidate in exercises_for_groups(requested_groups):
        if candidate.id == exercise.id:
            continue
        if _rank(candidate.impact) > _rank(max_impact):
            continue
        if _is_supine(candidate):
            continue
        if target_groups & {_value(g) for g in candidate.muscle_groups}:
            return candidate
    return None


def _entry_from_exercise(
    exercise: Exercise,
    language: str,
    max_impact: str,
    requested_groups: list[str],
    series: int = 3,
    reps: int = 10,
    weight: float = 0.0,
) -> dict[str, Any]:
    localized = _localized(exercise, language)
    blocked = _rank(exercise.impact) > _rank(max_impact)
    block_reason = ""
    substitute = ""
    if not blocked and _is_supine(exercise):
        blocked = True
        block_reason = _reason("supine", language)
    elif blocked:
        block_reason = _reason("impact", language)
    if blocked:
        replacement = _substitute_for(exercise, requested_groups, max_impact)
        if replacement is not None:
            substitute = localize(replacement.name, language)
    return {
        "exercise_original": localized["name"],
        "blocked": blocked,
        "block_reason": block_reason,
        "exercise_substitute": substitute,
        "series_adapted": min(max(int(series), 0), 3),
        "reps_adapted": max(int(reps), 10),
        "weight_suggested_kg": round(float(weight), 1),
        "exercise_id": exercise.id,
        "muscle_groups": list(exercise.muscle_groups),
        "impact": _value(exercise.impact),
        "description": localized["description"],
        "image_url": exercise.image_url,
        "media_url": exercise.media_url,
    }


def _resolve(item: dict[str, Any], by_id: dict[str, Exercise], by_name: dict[str, Exercise]) -> Exercise | None:
    exercise_id = item.get("exercise_id")
    if exercise_id and exercise_id in by_id:
        return by_id[exercise_id]
    name = str(item.get("exercise_original", "")).strip().lower()
    return by_name.get(name)


def build_offline_routine(
    request: RoutineRequest,
    core_result: EngineResult | None = None,
) -> dict[str, Any]:
    """Deterministic routine built only from the catalog (no model needed)."""
    language = _value(request.language)
    groups = [_value(g) for g in request.muscle_groups]
    max_impact = _max_impact(core_result)
    per_group = request.exercises_per_group or DEFAULT_EXERCISES_PER_GROUP

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in groups:
        candidates = exercises_for_groups([group])
        safe = [e for e in candidates if _rank(e.impact) <= _rank(max_impact)]
        pool = safe or candidates
        count = 0
        for exercise in pool:
            if exercise.id in seen:
                continue
            seen.add(exercise.id)
            entries.append(_entry_from_exercise(exercise, language, max_impact, groups))
            count += 1
            if count >= per_group:
                break

    payload: dict[str, Any] = {
        "schema_version": "1.1.0",
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "alerts": [],
        "routine": entries,
    }
    if core_result is not None:
        payload.update(
            {
                "phase_inferred": core_result.phase_inferred.value,
                "fatigue_level": core_result.fatigue_level.value,
                "k_load_multiplier": core_result.k_load,
            }
        )
    return payload


def enrich_routine(
    request: RoutineRequest,
    core_result: EngineResult | None,
    payload: dict[str, Any],
    catalog: list[Exercise],
) -> dict[str, Any]:
    """Correct and complete the model output using the catalog and the rules."""
    language = _value(request.language)
    groups = [_value(g) for g in request.muscle_groups]
    max_impact = _max_impact(core_result)
    by_id = {exercise.id: exercise for exercise in catalog}
    by_name: dict[str, Exercise] = {}
    for exercise in catalog:
        by_name[exercise.name.en.lower()] = exercise
        for code, value in (exercise.name.model_extra or {}).items():
            by_name[str(value).lower()] = exercise

    entries: list[dict[str, Any]] = []
    covered: set[str] = set()
    blocked_any = False
    for item in payload.get("routine", []) or []:
        if not isinstance(item, dict):
            continue
        exercise = _resolve(item, by_id, by_name)
        if exercise is None:
            continue
        entry = _entry_from_exercise(
            exercise,
            language,
            max_impact,
            groups,
            series=item.get("series_adapted", 3),
            reps=item.get("reps_adapted", 10),
            weight=item.get("weight_suggested_kg", 0.0),
        )
        blocked_any = blocked_any or entry["blocked"]
        covered.update(_value(g) for g in exercise.muscle_groups)
        entries.append(entry)

    # Complete any muscle group the model skipped.
    for group in groups:
        if any(group in {_value(g) for g in entry["muscle_groups"]} for entry in entries):
            continue
        fallback = build_offline_routine(
            RoutineRequest(
                muscle_groups=[group],
                language=language,
                exercises_per_group=1,
            ),
            core_result,
        )
        for entry in fallback["routine"]:
            blocked_any = blocked_any or entry["blocked"]
            entries.append(entry)

    alerts = list(payload.get("alerts", []) or [])
    if blocked_any:
        alerts.append(_ALERT_BLOCK.get(language.lower(), _ALERT_BLOCK["en"]))

    result: dict[str, Any] = {
        "schema_version": "1.1.0",
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "alerts": alerts,
        "routine": entries,
    }
    if core_result is not None:
        result.update(
            {
                "phase_inferred": core_result.phase_inferred.value,
                "fatigue_level": core_result.fatigue_level.value,
                "k_load_multiplier": core_result.k_load,
            }
        )
    return result


class RoutinePlanner:
    """Plans a routine with the model and validates/enforces it deterministically."""

    def __init__(self, client: ReasoningClient, cache_size: int = 128) -> None:
        self._client = client
        self._cache: LRUCache[str, RoutineResponse] = LRUCache(capacity=cache_size)

    @property
    def cache(self) -> LRUCache[str, RoutineResponse]:
        return self._cache

    def _key(self, request: RoutineRequest, core_result: EngineResult | None) -> str:
        return json.dumps(
            {
                "groups": [str(g) for g in request.muscle_groups],
                "language": _value(request.language),
                "per_group": request.exercises_per_group,
                "phase": core_result.phase_inferred.value if core_result else None,
                "k_load": core_result.k_load if core_result else None,
            },
            sort_keys=True,
        )

    def plan(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None = None,
    ) -> RoutineResponse:
        key = self._key(request, core_result)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        catalog = exercises_for_groups([_value(g) for g in request.muscle_groups])
        system_prompt = build_routine_system_prompt()
        user_prompt = build_routine_user_prompt(request, catalog, core_result)
        raw = self._client.complete(system_prompt, user_prompt, session_id=request.session_id)
        enriched = enrich_routine(request, core_result, raw, catalog)
        validated = RoutineResponse.model_validate(enriched)
        self._cache.put(key, validated)
        return validated

    def plan_offline(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None = None,
    ) -> RoutineResponse:
        return RoutineResponse.model_validate(build_offline_routine(request, core_result))


__all__ = [
    "DEFAULT_EXERCISES_PER_GROUP",
    "RoutinePlanner",
    "build_offline_routine",
    "enrich_routine",
]

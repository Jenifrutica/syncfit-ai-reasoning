"""Routine planning: muscle-group routines with deterministic safety.

The model picks exercise ids from the shared catalog; this module enriches the
output (localized name/description/image), enforces the biomechanical safety
rules and validates against `syncfit-contracts`. When the model omits groups or
entries, a deterministic catalog fallback completes the routine.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterable

from syncfit_contracts import (
    REQUIRED_PATTERNS,
    Exercise,
    RoutineRequest,
    RoutineResponse,
    exercises_for_groups,
    exercises_for_pattern,
    get_exercise,
    load_exercises,
    localize,
    patterns_of,
    required_patterns,
    exercise_required_equipment,
    variants_of,
)
from syncfit_core import EngineResult
from syncfit_core.enums import InferredPhase

from .client import ReasoningClient
from .loads import apply_baseline_loads
from .ordering import order_routine
from .prompts import build_routine_system_prompt, build_routine_user_prompt
from .structures import LRUCache

_IMPACT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
_REST_BY_IMPACT = {"HIGH": 150, "MEDIUM": 90, "LOW": 60}
DEFAULT_EXERCISES_PER_GROUP = 2
DEFAULT_EXERCISES_COUNT = 5
DEFAULT_EFFECTIVE_SETS = 3
DEFAULT_APPROXIMATION_SETS = 2
DEFAULT_REPS = 10
SECONDS_PER_REP = 3


def _rest_for(impact: object) -> int:
    return _REST_BY_IMPACT.get(_value(impact), 90)


def _set(set_type: str, reps: int, weight: float, rest: int) -> dict:
    return {
        "type": set_type,
        "reps": int(reps),
        "weight_kg": round(float(weight), 1),
        "rest_seconds": int(rest),
        "tempo": None,
        "estimated_seconds": int(reps * SECONDS_PER_REP + rest),
    }


def _build_sets(role: str, weight: float, impact: object) -> list[dict]:
    if role in ("WARMUP", "ACTIVATION"):
        set_type = "WARMUP" if role == "WARMUP" else "ACTIVATION"
        return [_set(set_type, 12, 0.0, 30) for _ in range(2)]
    rest = _rest_for(impact)
    sets = [
        _set("APPROXIMATION", DEFAULT_REPS, weight * (0.5 if i == 0 else 0.75), 60)
        for i in range(DEFAULT_APPROXIMATION_SETS)
    ]
    sets.extend(_set("EFFECTIVE", DEFAULT_REPS, weight, rest) for _ in range(DEFAULT_EFFECTIVE_SETS))
    return sets


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


def _localized_text(node) -> dict[str, str]:
    data = {"en": node.en}
    data.update(node.model_extra or {})
    return data


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
    rationale: str = "",
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
    role = _value(getattr(exercise, "role", "MAIN"))
    sets = _build_sets(role, float(weight), exercise.impact)
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
        "how_to": _localized_text(exercise.how_to or exercise.description),
        "tips": [_localized_text(t) for t in (exercise.tips or [])],
        "image_url": exercise.image_url,
        "media_url": exercise.media_url,
        "role": _value(getattr(exercise, "role", "MAIN")),
        "rest_seconds": _rest_for(exercise.impact),
        "estimated_seconds": sum(s["estimated_seconds"] for s in sets),
        "sets": sets,
        "movement_pattern": patterns_of(exercise),
        "compound": bool(getattr(exercise, "compound", False)),
        "rationale": rationale or "",
    }


def _resolve(item: dict[str, Any], by_id: dict[str, Exercise], by_name: dict[str, Exercise]) -> Exercise | None:
    exercise_id = item.get("exercise_id")
    if exercise_id and exercise_id in by_id:
        return by_id[exercise_id]
    name = str(item.get("exercise_original", "")).strip().lower()
    return by_name.get(name)


def _select_warmup(groups: list[str], limit: int = 2) -> list[Exercise]:
    selected: list[Exercise] = []
    seen: set[str] = set()
    for group in groups:
        for exercise in exercises_for_groups([group]):
            role = _value(getattr(exercise, "role", "MAIN"))
            if role in ("WARMUP", "ACTIVATION") and exercise.id not in seen:
                seen.add(exercise.id)
                selected.append(exercise)
                if len(selected) >= limit:
                    return selected
    if len(selected) < limit:
        for exercise in load_exercises():
            role = _value(getattr(exercise, "role", "MAIN"))
            if role in ("WARMUP", "ACTIVATION") and exercise.id not in seen:
                seen.add(exercise.id)
                selected.append(exercise)
                if len(selected) >= limit:
                    break
    return selected


def _trim_to_budget(routine: list[dict[str, Any]], budget_seconds: int) -> list[dict[str, Any]]:
    trimmed = list(routine)
    while trimmed and sum(e["estimated_seconds"] for e in trimmed) > budget_seconds:
        trimmed.pop()
    return trimmed


def build_offline_routine(
    request: RoutineRequest,
    core_result: EngineResult | None = None,
) -> dict[str, Any]:
    """Deterministic, pattern-based routine built only from the catalog (no model)."""
    return build_prescription(request, core_result)



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

    warmup: list[dict[str, Any]] = []
    if request.include_warmup:
        warmup = [
            _entry_from_exercise(e, language, max_impact, groups)
            for e in _select_warmup(groups, 2)
        ]

    if request.time_budget_minutes:
        warmup_seconds = sum(e["estimated_seconds"] for e in warmup)
        entries = _trim_to_budget(
            entries, max(request.time_budget_minutes * 60 - warmup_seconds, 0)
        )

    entries = order_routine(
        entries, core_result.phase_inferred.value if core_result is not None else None, language
    )
    total = sum(e["estimated_seconds"] for e in warmup + entries)
    result: dict[str, Any] = {
        "schema_version": "1.2.0",
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "alerts": alerts,
        "total_estimated_minutes": round(total / 60, 1),
        "warmup": warmup,
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


# Evidence-based prescription schemes per objective (sets x reps, rest seconds).
# Sources: Schoenfeld 2017/2021 (hypertrophy volume/intensity), Baz-Valle 2022,
# Currier 2023 (rest intervals), ACSM (compounds first, progressive overload).
_GOAL_SCHEME: dict[str, dict[str, int]] = {
    "STRENGTH": {"sets": 4, "reps": 5, "rest_compound": 180, "rest_iso": 120},
    "HYPERTROPHY": {"sets": 3, "reps": 10, "rest_compound": 120, "rest_iso": 75},
    "PERFORMANCE": {"sets": 3, "reps": 8, "rest_compound": 120, "rest_iso": 75},
    "FAT_LOSS": {"sets": 3, "reps": 14, "rest_compound": 75, "rest_iso": 45},
    "HEALTH": {"sets": 3, "reps": 12, "rest_compound": 75, "rest_iso": 45},
    "RECOVERY": {"sets": 2, "reps": 12, "rest_compound": 60, "rest_iso": 45},
    "GESTATIONAL_HEALTH": {"sets": 3, "reps": 12, "rest_compound": 75, "rest_iso": 60},
}

# Why each pattern is included (localized, evidence-informed).
_PATTERN_REASON: dict[str, dict[str, str]] = {
    "hinge": {"en": "Hip-hinge for posterior chain/glutes (deadlift/RDL).",
              "es": "Bisagra de cadera para cadena posterior/glúteos (peso muerto/RDL).",
              "zh": "髋铰链训练后链与臀部（硬拉/RDL）。"},
    "lunge": {"en": "Unilateral work for glutes/quads and stability (Bulgarian/split squat).",
              "es": "Trabajo unilateral para glúteos/cuádriceps y estabilidad (búlgara).",
              "zh": "单侧训练臀部/股四头肌与稳定（保加利亚分腿蹲）。"},
    "hip_thrust": {"en": "Hip thrust: high glute activation at short muscle length (Contreras 2016).",
                   "es": "Hip thrust: alta activación glútea en longitud corta (Contreras 2016).",
                   "zh": "臀推：短肌长下高臀肌激活（Contreras 2016）。"},
    "glute_kickback": {"en": "Glute kickback to bias the gluteus maximus.",
                       "es": "Patada de glúteo para enfatizar el glúteo mayor.",
                       "zh": "后踢腿强调臀大肌。"},
    "hip_abduction": {"en": "Hip abduction to target gluteus medius/minimus.",
                      "es": "Abducción para glúteo medio/menor.",
                      "zh": "髋外展针对臀中/小肌。"},
    "squat": {"en": "Squat pattern: primary quadriceps/glute compound.",
              "es": "Patrón de sentadilla: compuesto principal de cuádriceps/glúteo.",
              "zh": "深蹲：股四头肌/臀部的核心复合动作。"},
    "leg_extension": {"en": "Knee extension isolation for the quadriceps.",
                      "es": "Extensión de rodilla como aislamiento de cuádriceps.",
                      "zh": "腿屈伸孤立股四头肌。"},
    "leg_curl": {"en": "Knee flexion isolation for the hamstrings.",
                 "es": "Curl femoral como aislamiento de isquios.",
                 "zh": "腿弯举孤立腘绳肌。"},
    "glute_ham": {"en": "Hip extension + knee flexion for hamstrings/glutes.",
                  "es": "Extensión de cadera + flexión de rodilla para isquios/glúteos.",
                  "zh": "髋伸与屈膝训练腘绳肌/臀部。"},
    "pull_vertical": {"en": "Vertical pull for lats (pulldown/pull-up).",
                      "es": "Tracción vertical para dorsales (jalón/dominada).",
                      "zh": "垂直拉训练背阔肌。"},
    "row": {"en": "Horizontal pull for mid-back/posture.",
            "es": "Tracción horizontal para espalda media/postura.",
            "zh": "水平拉训练中背。"},
    "bench_press": {"en": "Horizontal push for chest/triceps.",
                    "es": "Empuje horizontal para pecho/tríceps.",
                    "zh": "水平推训练胸/三头。"},
    "overhead_press": {"en": "Vertical push for shoulders.",
                       "es": "Empuje vertical para hombros.",
                       "zh": "垂直推训练肩部。"},
    "lateral_raise": {"en": "Lateral raise for deltoid width.",
                      "es": "Elevación lateral para anchura del deltoides.",
                      "zh": "侧平举增加三角肌宽度。"},
    "biceps": {"en": "Elbow flexion isolation for the biceps.",
               "es": "Flexión de codo como aislamiento de bíceps.",
               "zh": "弯举孤立肱二头肌。"},
    "triceps": {"en": "Elbow extension isolation for the triceps.",
                "es": "Extensión de codo como aislamiento de tríceps.",
                "zh": "臂屈伸孤立肱三头肌。"},
    "calf_raise": {"en": "Plantarflexion for the calves.",
                   "es": "Flexión plantar para gemelos.",
                   "zh": "提踵训练小腿。"},
    "hip_adduction": {"en": "Hip adduction for the adductors.",
                      "es": "Aducción para aductores.",
                      "zh": "髋内收训练内收肌。"},
    "core_plank": {"en": "Anti-extension core stability.",
                   "es": "Estabilidad del core anti-extensión.",
                   "zh": "抗伸展核心稳定。"},
    "core_deadbug": {"en": "Anti-extension core control.",
                     "es": "Control del core anti-extensión.",
                     "zh": "抗伸展核心控制。"},
    "core_hanging": {"en": "Hip flexion for the lower abs.",
                     "es": "Flexión de cadera para abdomen bajo.",
                     "zh": "屈髋训练下腹。"},
}


def _scheme(objective: object) -> dict[str, int]:
    key = _value(objective) if objective is not None else "HYPERTROPHY"
    return _GOAL_SCHEME.get(key, _GOAL_SCHEME["HYPERTROPHY"])


def _pattern_reason(pattern: str | None, language: str) -> str:
    if not pattern:
        return ""
    table = _PATTERN_REASON.get(pattern)
    if not table:
        return ""
    return table.get(language.lower(), table["en"])


def _build_sets_goal(role: str, weight: float, impact: object, compound: bool, objective: object) -> list[dict]:
    if role in ("WARMUP", "ACTIVATION"):
        set_type = "WARMUP" if role == "WARMUP" else "ACTIVATION"
        return [_set(set_type, 12, 0.0, 30) for _ in range(2)]
    scheme = _scheme(objective)
    rest = scheme["rest_compound"] if compound else scheme["rest_iso"]
    reps = scheme["reps"]
    sets = [
        _set("APPROXIMATION", reps, weight * (0.5 if i == 0 else 0.75), 60)
        for i in range(DEFAULT_APPROXIMATION_SETS)
    ]
    sets.extend(_set("EFFECTIVE", reps, weight, rest) for _ in range(scheme["sets"]))
    return sets


def _safe(
    exercise: Exercise,
    max_impact: str,
    blocked_patterns: set[str],
    equipment: set[str] | None = None,
    allowed_ids: set[str] | None = None,
) -> bool:
    if _value(getattr(exercise, "role", "MAIN")) != "MAIN":
        return False
    if _rank(exercise.impact) > _rank(max_impact):
        return False
    if _is_supine(exercise):
        return False
    if patterns_of(exercise) in blocked_patterns:
        return False
    return True


def _availability_rank(
    exercise: Exercise, equipment: set[str] | None, allowed_ids: set[str] | None
) -> int:
    """0 when the exercise is doable with the gym inventory, else 1 (soft priority)."""
    if equipment is None:
        return 0
    if allowed_ids and exercise.id in allowed_ids:
        return 0
    required = exercise_required_equipment(exercise)
    return 0 if (required <= equipment or required <= {"none"}) else 1


def build_prescription(
    request: RoutineRequest,
    core_result: EngineResult | None = None,
    *,
    contraindicated_patterns: Iterable[str] = (),
    preferred_exercise_ids: Iterable[str] = (),
    equipment_keys: Iterable[str] | None = None,
    available_exercise_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Deterministic, evidence-based routine driven by movement patterns.

    Guarantees: one exercise per movement pattern (no duplicates), required-pattern
    coverage up to the requested size, compounds ordered first, and contraindicated
    patterns excluded. The reasoning model may later choose among valid variants.
    """
    language = _value(request.language)
    groups = [_value(g) for g in request.muscle_groups]
    max_impact = _max_impact(core_result)
    blocked = {_value(p) for p in contraindicated_patterns}
    preferred = {str(x) for x in preferred_exercise_ids}
    equipment = {_value(k) for k in equipment_keys} if equipment_keys is not None else None
    allowed = {str(x) for x in available_exercise_ids or []}
    # Patterns the athlete's gym machines can cover are prioritised (stable order).
    preferred_patterns = {
        patterns_of(e) for e in load_exercises() if e.id in preferred and patterns_of(e)
    }
    target = request.exercises_count or DEFAULT_EXERCISES_COUNT
    per_group = request.exercises_per_group or max(1, -(-target // len(groups)))

    selected: list[Exercise] = []
    used_ids: set[str] = set()
    used_patterns: set[str] = set()

    def add(exercise: Exercise) -> None:
        selected.append(exercise)
        used_ids.add(exercise.id)
        pattern = patterns_of(exercise)
        if pattern:
            used_patterns.add(pattern)

    for group in groups:
        count = 0
        group_patterns = sorted(
            [
                p
                for p in REQUIRED_PATTERNS.get(group, ())
                if p not in blocked and p not in used_patterns
            ],
            key=lambda p: 0 if p in preferred_patterns else 1,
        )
        for pattern in group_patterns:
            candidates = [
                e for e in exercises_for_pattern(pattern, [group]) if _safe(e, max_impact, blocked)
            ]
            if not candidates:
                continue
            candidates.sort(
                key=lambda e: (
                    0 if e.id in preferred else 1,
                    _availability_rank(e, equipment, allowed),
                    e.id,
                )
            )
            add(candidates[0])
            count += 1
            if count >= per_group:
                break
        if count < per_group:
            for exercise in exercises_for_groups([group]):
                if exercise.id in used_ids or not _safe(exercise, max_impact, blocked, equipment, allowed):
                    continue
                pattern = patterns_of(exercise)
                if pattern and pattern in used_patterns:
                    continue
                add(exercise)
                count += 1
                if count >= per_group:
                    break
        if len(selected) >= target:
            break

    selected = selected[:target]

    entries = [
        _entry_from_exercise(
            exercise,
            language,
            max_impact,
            groups,
            series=_scheme(request.objective)["sets"],
            reps=_scheme(request.objective)["reps"],
            rationale=_pattern_reason(patterns_of(exercise), language),
        )
        for exercise in selected
    ]

    warmup: list[dict[str, Any]] = []
    if request.include_warmup:
        warmup = [
            _entry_from_exercise(e, language, max_impact, groups)
            for e in _select_warmup(groups, 2)
        ]

    if request.time_budget_minutes:
        warmup_seconds = sum(e["estimated_seconds"] for e in warmup)
        entries = _trim_to_budget(entries, max(request.time_budget_minutes * 60 - warmup_seconds, 0))

    entries = order_routine(entries, core_result.phase_inferred.value if core_result else None, language)
    total = sum(e["estimated_seconds"] for e in warmup + entries)

    covered = [p for p in required_patterns(groups) if p in used_patterns]
    alerts: list[str] = []
    if blocked:
        alerts.append("Contraindicated patterns excluded: " + ", ".join(sorted(blocked)))
    if covered:
        alerts.append("Patterns covered: " + ", ".join(covered))

    payload: dict[str, Any] = {
        "schema_version": "1.2.0",
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "alerts": alerts,
        "total_estimated_minutes": round(total / 60, 1),
        "warmup": warmup,
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


_ID_RE = re.compile(r"[^a-z0-9]+")


def _normalize_id(raw: object) -> str:
    """Normalize model-provided ids/names (underscores, spaces, case)."""
    return _ID_RE.sub("-", str(raw or "").strip().lower()).strip("-")


def _catalog_index(catalog: list[Exercise]) -> tuple[dict[str, Exercise], dict[str, Exercise]]:
    by_id: dict[str, Exercise] = {}
    by_name: dict[str, Exercise] = {}
    for exercise in catalog:
        by_id[_normalize_id(exercise.id)] = exercise
        for value in [exercise.name.en, *(exercise.name.model_extra or {}).values()]:
            by_name[_normalize_id(value)] = exercise
    return by_id, by_name


def _sets_from(role: str, series: int, reps: int, rest: int, weight: float) -> list[dict]:
    if role in ("WARMUP", "ACTIVATION"):
        set_type = "WARMUP" if role == "WARMUP" else "ACTIVATION"
        return [_set(set_type, 12, 0.0, 30) for _ in range(2)]
    sets = [
        _set("APPROXIMATION", reps, weight * (0.5 if i == 0 else 0.75), 60)
        for i in range(DEFAULT_APPROXIMATION_SETS)
    ]
    sets.extend(_set("EFFECTIVE", reps, weight, rest) for _ in range(max(1, series)))
    return sets


def _clamp(value: object, low: int, high: int, default: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _entry_from_model_item(
    exercise: Exercise, item: dict[str, Any], language: str, max_impact: str, groups: list[str]
) -> dict[str, Any]:
    series = _clamp(item.get("series"), 1, 6, 3)
    reps = _clamp(item.get("reps"), 1, 30, 10)
    entry = _entry_from_exercise(
        exercise,
        language,
        max_impact,
        groups,
        series=series,
        reps=reps,
        weight=item.get("weight_suggested_kg", 0.0),
        rationale=str(item.get("rationale", "")),
    )
    rest = _clamp(item.get("rest_seconds"), 15, 300, entry["rest_seconds"])
    sets = _sets_from(entry["role"], series, reps, rest, entry["weight_suggested_kg"])
    entry["series_adapted"] = series
    entry["reps_adapted"] = reps
    entry["rest_seconds"] = rest
    entry["sets"] = sets
    entry["estimated_seconds"] = sum(s["estimated_seconds"] for s in sets)
    return entry


def build_design_prompt(
    request: RoutineRequest,
    core_result: EngineResult | None,
    assessment: dict[str, Any] | None,
    gym_machines: list[dict[str, Any]] | None,
    contraindicated: set[str],
    equipment_keys: Iterable[str] | None = None,
) -> tuple[str, str]:
    """DeepSeek designs the whole routine from the local-model state + evidence."""
    language = _value(request.language)
    groups = [_value(g) for g in request.muscle_groups]
    catalog = exercises_for_groups(groups)
    scheme = _scheme(request.objective)
    wanted_patterns = [p for p in required_patterns(groups) if p not in contraindicated]

    catalog_rows = [
        {
            "id": e.id,
            "name": e.name.en,
            "muscle_groups": [str(g) for g in e.muscle_groups],
            "movement_pattern": patterns_of(e),
            "compound": bool(getattr(e, "compound", False)),
            "impact": str(e.impact),
            "equipment_type": str(e.equipment_type) if e.equipment_type else None,
        }
        for e in catalog
    ]
    payload = {
        "language": language,
        "objective": _value(request.objective) if request.objective else "HYPERTROPHY",
        "muscle_groups": groups,
        "exercises_count": request.exercises_count or DEFAULT_EXERCISES_COUNT,
        "modality": _value(request.modality) if request.modality else None,
        "day_or_week": request.day_or_week,
        "phase_inferred": core_result.phase_inferred.value if core_result else (assessment or {}).get("phase_inferred"),
        "fatigue_level": core_result.fatigue_level.value if core_result else (assessment or {}).get("fatigue_level"),
        "k_load_multiplier": core_result.k_load if core_result else (assessment or {}).get("k_load_multiplier"),
        "autonomic_status": (assessment or {}).get("autonomic_status"),
        "articular_risk_pct": (assessment or {}).get("articular_risk_pct"),
        "contraindicated_patterns": sorted(contraindicated),
        "required_patterns": wanted_patterns,
        "gym_machines": gym_machines or [],
        "gym_equipment": sorted({str(k) for k in equipment_keys}) if equipment_keys is not None else None,
        "prescription_ranges": scheme,
        "catalog": catalog_rows,
    }
    system = (
        "You are the prescriptive analytical engine of SyncFit Edge (a strength-coaching kernel, "
        "NOT a chatbot). You design evidence-based training routines for women across the menstrual "
        "cycle and pregnancy. Reason first about patterns, then choose exercises and dose. "
        "Output MUST be a single strict JSON object with no prose or markdown."
    )
    user = (
        "Design the routine. Hard rules:\n"
        "- Choose exercise ids ONLY from the provided catalog (never invent ids).\n"
        "- Cover every required pattern (up to the exercise count). NEVER repeat a movement_pattern.\n"
        "- Order compounds before isolation; activation/warm-up first.\n"
        "- Exclude contraindicated patterns; respect phase safety (no high impact in ovulatory/3rd trimester,\n"
        "  no supine from gestational week 16).\n"
        "- Equipment filters, in order: (1) exercises covered by the gym machines;\n"
        "  (2) free exercises whose required_equipment is available in gym_equipment\n"
        "  (bench enables Bulgarian/step-ups; dumbbell/barbell/smith as registered);\n"
        "  (3) bodyweight only as a last resort. Never pick an exercise whose equipment is missing.\n"
        "- Machine-first: if a gym machine covers a pattern, use its exercise id as the first option.\n"
        "- Echo k_load_multiplier/fatigue_level/phase_inferred from the data; never recompute k_load.\n"
        "- Dose sets/reps/rest within prescription_ranges and the goal.\n"
        "Return JSON:\n"
        '{"summary":"<why this routine>",'
        '"warmup":[{"exercise_id":"","series":2,"reps":12,"rest_seconds":30}],'
        '"routine":[{"exercise_id":"","movement_pattern":"","series":3,"reps":10,"rest_seconds":90,'
        '"weight_suggested_kg":0,"rationale":"<evidence-based why>"}]}\n\n'
        f"Input:\n{json.dumps(payload, ensure_ascii=False)}"
    )
    return system, user


def enforce_prescription(
    request: RoutineRequest,
    core_result: EngineResult | None,
    model_payload: dict[str, Any],
    skeleton: dict[str, Any],
    contraindicated_patterns: Iterable[str] = (),
    preferred_exercise_ids: Iterable[str] = (),
    gym_machines: list[dict[str, Any]] | None = None,
    equipment_keys: Iterable[str] | None = None,
    available_exercise_ids: Iterable[str] | None = None,
) -> dict[str, Any]:
    """Repair/validate the model's routine so all invariants always hold."""
    language = _value(request.language)
    groups = [_value(g) for g in request.muscle_groups]
    max_impact = _max_impact(core_result)
    blocked = {_value(p) for p in contraindicated_patterns}
    equipment = {_value(k) for k in equipment_keys} if equipment_keys is not None else None
    allowed = {str(x) for x in available_exercise_ids or []}
    target = request.exercises_count or DEFAULT_EXERCISES_COUNT
    catalog_all = load_exercises()
    global_by_id, global_by_name = _catalog_index(catalog_all)
    by_id, by_name = _catalog_index(exercises_for_groups(groups))

    def resolve(raw: object) -> Exercise | None:
        key = _normalize_id(raw)
        return by_id.get(key) or by_name.get(key) or global_by_id.get(key) or global_by_name.get(key)

    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in model_payload.get("routine") or []:
        if not isinstance(item, dict):
            continue
        exercise = resolve(item.get("exercise_id")) or resolve(item.get("exercise_original"))
        if exercise is None or not _safe(exercise, max_impact, blocked):
            continue
        pattern = patterns_of(exercise)
        if pattern and pattern in seen:
            continue
        if pattern:
            seen.add(pattern)
        entries.append(_entry_from_model_item(exercise, item, language, max_impact, groups))

    # Machine-first: force the gym machine variant for patterns it covers.
    machine_pattern: dict[str, str] = {}
    for machine in gym_machines or []:
        if machine.get("pattern") and machine.get("exercise_id"):
            machine_pattern.setdefault(str(machine["pattern"]), str(machine["exercise_id"]))
    for pattern, exercise_id in machine_pattern.items():
        exercise = global_by_id.get(_normalize_id(exercise_id))
        if exercise is None or not _safe(exercise, max_impact, blocked):
            continue
        index = next((i for i, e in enumerate(entries) if e.get("movement_pattern") == pattern), None)
        if index is not None:
            current = entries[index]
            if current.get("exercise_id") != exercise.id:
                rebuilt = _entry_from_exercise(
                    exercise, language, max_impact, groups,
                    series=current["series_adapted"], reps=current["reps_adapted"],
                    weight=current["weight_suggested_kg"], rationale=current.get("rationale", ""),
                )
                rebuilt["sets"] = _sets_from(rebuilt["role"], current["series_adapted"], current["reps_adapted"],
                                             current["rest_seconds"], rebuilt["weight_suggested_kg"])
                rebuilt["estimated_seconds"] = sum(s["estimated_seconds"] for s in rebuilt["sets"])
                entries[index] = rebuilt
        elif len(entries) < target:
            entry = _entry_from_exercise(exercise, language, max_impact, groups)
            entries.append(entry)
            seen.add(pattern)

    # Coverage: complete missing required patterns from the deterministic skeleton.
    skeleton_by_pattern = {
        e.get("movement_pattern"): e for e in (skeleton.get("routine") or []) if e.get("movement_pattern")
    }
    for pattern in required_patterns(groups):
        if pattern in blocked or pattern in seen or len(entries) >= target:
            continue
        fallback = skeleton_by_pattern.get(pattern)
        if fallback:
            entries.append(fallback)
            seen.add(pattern)

    entries = entries[:target]
    entries = order_routine(entries, core_result.phase_inferred.value if core_result else None, language)

    warmup = skeleton.get("warmup", []) if request.include_warmup else []
    total = sum(e["estimated_seconds"] for e in warmup + entries)
    alerts: list[str] = []
    summary = model_payload.get("summary")
    if isinstance(summary, str) and summary:
        alerts.append(summary)
    if blocked:
        alerts.append("Contraindicated patterns excluded: " + ", ".join(sorted(blocked)))

    payload: dict[str, Any] = {
        "schema_version": "1.2.0",
        "session_id": request.session_id,
        "language": language,
        "muscle_groups": groups,
        "alerts": alerts,
        "total_estimated_minutes": round(total / 60, 1),
        "warmup": warmup,
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


def alternatives_for(
    exercise_id: str,
    equipment_keys: Iterable[str] | None = None,
    language: str = "EN",
) -> list[dict[str, Any]]:
    """Ordered replacement options for an exercise (for the UI "Change" button).

    Same movement pattern and interchangeable variants come first; exercises the
    athlete's equipment supports are listed before the rest.
    """
    base = get_exercise(exercise_id)
    if base is None:
        return []
    pattern = patterns_of(base)
    family = {e.id for e in variants_of(exercise_id)}
    available = {_value(k) for k in equipment_keys} if equipment_keys is not None else None

    def is_available(exercise: Exercise) -> bool:
        if available is None:
            return True
        required = exercise_required_equipment(exercise)
        return required <= available or required <= {"none"}

    pool = [
        e for e in load_exercises()
        if e.id != exercise_id and (patterns_of(e) == pattern or e.id in family)
    ]

    def sort_key(exercise: Exercise) -> tuple:
        return (0 if is_available(exercise) else 1, 0 if exercise.id in family else 1, exercise.id)

    pool.sort(key=sort_key)
    options: list[dict[str, Any]] = []
    for exercise in pool:
        required = sorted(exercise_required_equipment(exercise))
        options.append(
            {
                "id": exercise.id,
                "name": localize(exercise.name, language),
                "movement_pattern": patterns_of(exercise),
                "equipment_type": str(exercise.equipment_type) if exercise.equipment_type else None,
                "required_equipment": required,
                "available": is_available(exercise),
                "variant_of": getattr(exercise, "variant_of", None),
                "image_url": exercise.image_url,
            }
        )
    return options


class RoutinePlanner:
    """DeepSeek designs the routine; the deterministic layer validates/repairs it."""

    def __init__(self, client: ReasoningClient, cache_size: int = 128) -> None:
        self._client = client
        self._cache: LRUCache[str, RoutineResponse] = LRUCache(capacity=cache_size)

    @property
    def cache(self) -> LRUCache[str, RoutineResponse]:
        return self._cache

    def _key(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None,
        contraindicated: tuple[str, ...],
        preferred: tuple[str, ...],
    ) -> str:
        return json.dumps(
            {
                "groups": [str(g) for g in request.muscle_groups],
                "language": _value(request.language),
                "per_group": request.exercises_per_group,
                "count": request.exercises_count,
                "objective": _value(request.objective) if request.objective else None,
                "phase": core_result.phase_inferred.value if core_result else None,
                "k_load": core_result.k_load if core_result else None,
                "contra": sorted(contraindicated),
                "preferred": sorted(preferred),
            },
            sort_keys=True,
        )

    def _refine(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None,
        skeleton: dict[str, Any],
        groups: list[str],
        blocked: set[str],
        preferred: set[str] | None = None,
        gym_machines: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Ask the model to choose among valid variants per slot (evidence-bounded).

        The deterministic skeleton fixes patterns, coverage, sets/reps/rest and
        safety; the model only swaps an exercise for an equivalent variation of the
        SAME movement pattern. Any choice outside the allowed candidates is ignored.
        """
        entries = skeleton.get("routine", []) or []
        if not entries:
            return skeleton
        catalog = exercises_for_groups(groups)
        max_impact = _max_impact(core_result)

        preferred_ids = preferred or set()
        slots: list[dict[str, Any]] = []
        allowed: dict[str, set[str]] = {}
        for index, entry in enumerate(entries):
            pattern = entry.get("movement_pattern")
            current_id = str(entry.get("exercise_id") or "")
            if current_id and current_id in preferred_ids:
                # Locked: the athlete's gym machine covers this pattern.
                candidates = [current_id]
            else:
                candidates = sorted(
                    e.id
                    for e in catalog
                    if _safe(e, max_impact, blocked, equipment, allowed) and patterns_of(e) == pattern
                )
            allowed[str(index)] = set(candidates)
            slots.append(
                {
                    "index": index,
                    "movement_pattern": pattern,
                    "current": entry.get("exercise_id"),
                    "candidates": candidates,
                }
            )

        user = (
            "You are refining a pre-validated, evidence-based routine. For each slot you may "
            "replace the exercise ONLY with another candidate of the SAME movement_pattern "
            "(equipment variants: barbell/Smith/machine/dumbbell/cable). Do not change patterns, "
            "sets, reps, rest or safety. Choose the option that best fits an athlete training for "
            f"goal={_value(request.objective) if request.objective else 'HYPERTROPHY'}.\n"
            "The athlete's gym machines are given; when a slot's current exercise is one of them "
            "(or a machine covers that pattern) keep the machine variant (it is the first option "
            "and the athlete can switch manually later).\n\n"
            f"athlete_machines:\n{json.dumps(gym_machines or [], ensure_ascii=False)}\n\n"
            f"Slots:\n{json.dumps(slots, ensure_ascii=False)}\n\n"
            'Return ONLY JSON: {"choices": {"<index>": "<candidate id>"}, "summary": "<short rationale>"}'
        )
        try:
            raw = self._client.complete(
                "You are the prescriptive analytical engine of SyncFit Edge. Return only JSON.",
                user,
                session_id=request.session_id,
            )
        except Exception:
            return skeleton

        choices = raw.get("choices") if isinstance(raw, dict) else None
        if not isinstance(choices, dict):
            return skeleton
        by_id = {e.id: e for e in catalog}
        for index_str, chosen in choices.items():
            if str(index_str) not in allowed or chosen not in allowed[str(index_str)]:
                continue
            index = int(index_str)
            exercise = by_id.get(str(chosen))
            if exercise is None:
                continue
            current = entries[index]
            entries[index] = _entry_from_exercise(
                exercise,
                _value(request.language),
                max_impact,
                groups,
                series=current.get("series_adapted", 3),
                reps=current.get("reps_adapted", 10),
                weight=current.get("weight_suggested_kg", 0.0),
                rationale=_pattern_reason(patterns_of(exercise), _value(request.language)),
            )
            # Preserve the gym machine mapping decided by the backend, if any.
            for key in ("machine_id", "machine_name", "image_url"):
                if key in current and current[key] is not None:
                    entries[index][key] = current[key]
        summary = raw.get("summary")
        if isinstance(summary, str) and summary:
            skeleton.setdefault("alerts", []).append(summary)
        return skeleton

    def plan(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None = None,
        baseline_loads: list[Any] | None = None,
        contraindicated_patterns: Iterable[str] = (),
        preferred_exercise_ids: Iterable[str] = (),
        gym_machines: list[dict[str, Any]] | None = None,
        assessment: dict[str, Any] | None = None,
        equipment_keys: Iterable[str] | None = None,
        available_exercise_ids: Iterable[str] | None = None,
    ) -> RoutineResponse:
        contraindicated = tuple(sorted(_value(p) for p in contraindicated_patterns))
        preferred = tuple(sorted(str(p) for p in preferred_exercise_ids))
        key = self._key(request, core_result, contraindicated, preferred)
        cached = self._cache.get(key)
        if cached is not None:
            return cached

        # Deterministic evidence skeleton: guarantees invariants and is the fallback.
        skeleton = build_prescription(
            request,
            core_result,
            contraindicated_patterns=contraindicated,
            preferred_exercise_ids=preferred,
            equipment_keys=equipment_keys,
            available_exercise_ids=available_exercise_ids,
        )

        self._last_engine = "deterministic"
        enriched = skeleton
        try:
            system, user = build_design_prompt(
                request, core_result, assessment, gym_machines, set(contraindicated), equipment_keys
            )
            raw = self._client.complete(system, user, session_id=request.session_id)
            if isinstance(raw, dict) and raw.get("routine"):
                enriched = enforce_prescription(
                    request,
                    core_result,
                    raw,
                    skeleton,
                    contraindicated_patterns=contraindicated,
                    preferred_exercise_ids=preferred,
                    gym_machines=gym_machines,
                    equipment_keys=equipment_keys,
                    available_exercise_ids=available_exercise_ids,
                )
                self._last_engine = "deepseek"
        except Exception:
            enriched = skeleton
            self._last_engine = "deterministic"

        if baseline_loads:
            enriched["warmup"] = apply_baseline_loads(
                enriched.get("warmup", []), baseline_loads, core_result, request.energy_level
            )
            enriched["routine"] = apply_baseline_loads(
                enriched.get("routine", []), baseline_loads, core_result, request.energy_level
            )
        validated = RoutineResponse.model_validate(enriched)
        self._cache.put(key, validated)
        return validated

    @property
    def last_engine(self) -> str:
        return getattr(self, "_last_engine", "deterministic")

    def plan_offline(
        self,
        request: RoutineRequest,
        core_result: EngineResult | None = None,
        baseline_loads: list[Any] | None = None,
        contraindicated_patterns: Iterable[str] = (),
        preferred_exercise_ids: Iterable[str] = (),
    ) -> RoutineResponse:
        payload = build_prescription(
            request,
            core_result,
            contraindicated_patterns=contraindicated_patterns,
            preferred_exercise_ids=preferred_exercise_ids,
        )
        if baseline_loads:
            payload["warmup"] = apply_baseline_loads(
                payload.get("warmup", []), baseline_loads, core_result, request.energy_level
            )
            payload["routine"] = apply_baseline_loads(
                payload.get("routine", []), baseline_loads, core_result, request.energy_level
            )
        return RoutineResponse.model_validate(payload)


__all__ = [
    "DEFAULT_EXERCISES_PER_GROUP",
    "RoutinePlanner",
    "build_offline_routine",
    "build_prescription",
    "build_design_prompt",
    "enforce_prescription",
    "alternatives_for",
    "enrich_routine",
]

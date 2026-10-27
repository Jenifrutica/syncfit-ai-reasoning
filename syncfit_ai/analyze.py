"""AI analysis helpers: infer machine info and interpret symptoms from text."""

from __future__ import annotations

import json
from typing import Any

from .client import OpenCodeGoClient

MACHINE_SYSTEM = (
    "You are a gym equipment expert. Return ONLY a JSON object with: "
    '{"inferred_type": "FREE_WEIGHT|MACHINE|SMITH|CABLE|BODYWEIGHT|ASSISTED|BAND|NONE", '
    '"name": {"en": "...", "es": "...", "zh": "..."}, '
    '"purpose": {"en": "...", "es": "...", "zh": "..."}, '
    '"exercise_ids": ["catalog movements this machine covers"], '
    '"weight_factor": number}. '
    "The admin may type in any language: translate `name` and `purpose` into "
    "English, Spanish and Chinese (English is required). Infer `exercise_ids` "
    "using common catalog exercise ids, and PREFER the variant that matches the "
    "equipment in the name (e.g. 'hip thrust machine' -> hip-thrust-machine; "
    "'smith ...' -> smith-hip-thrust/smith-squat; 'cable ...' -> cable-*; "
    "'leg press' -> leg-press; 'dumbbell ...' -> db-*). List the best-matching "
    "machine variant first, then other compatible movements."
)

SYMPTOM_SYSTEM = (
    "Eres un clinico de ejercicio femenino. Recibe sintomas con intensidad 1-10 y notas libres. "
    "Devuelve SOLO JSON: {\"absolute_contraindication\": bool, "
    "\"guidance\": \"consejo breve\", \"avoid\": [\"tipos de ejercicio a evitar\"]}. "
    "Marca absolute_contraindication=true SOLO en casos muy riesgosos (p.ej. dilatacion, "
    "sangrado, contracciones regulares). Si es asi, recomienda lo mas suave (movilidad, "
    "estiramientos) sin dejar de estar activa."
)


MACHINE_TYPES = {"FREE_WEIGHT", "MACHINE", "SMITH", "CABLE", "BODYWEIGHT", "ASSISTED", "BAND", "NONE"}
WEIGHT_FACTOR_RANGE = (0.25, 3.0)


def _clean_machine_info(info: Any) -> dict:
    """Drop fields the model returned with an invalid value so callers use their defaults."""
    if not isinstance(info, dict):
        return {}
    clean = dict(info)
    if str(clean.get("inferred_type", "")).upper() in MACHINE_TYPES:
        clean["inferred_type"] = str(clean["inferred_type"]).upper()
    else:
        clean.pop("inferred_type", None)
    try:
        factor = float(clean["weight_factor"])
        low, high = WEIGHT_FACTOR_RANGE
        if not low <= factor <= high:
            raise ValueError
        clean["weight_factor"] = factor
    except (KeyError, TypeError, ValueError):
        clean.pop("weight_factor", None)
    ids = clean.get("exercise_ids")
    clean["exercise_ids"] = [str(i) for i in ids if i] if isinstance(ids, list) else []
    return clean


def analyze_machine(name: str, description: str | None = None, language: str = "EN", client: Any | None = None) -> dict:
    """Infer a machine's type, localized name/purpose, exercises and weight factor."""
    client = client or OpenCodeGoClient()
    user = f"language={language}\nname={name}\ndescription={description or ''}"
    return _clean_machine_info(client.complete(MACHINE_SYSTEM, user))


def analyze_symptoms(symptoms: list[dict], language: str = "EN", client: Any | None = None) -> dict:
    client = client or OpenCodeGoClient()
    user = f"language={language}\nsymptoms={json.dumps(symptoms, ensure_ascii=False)}"
    return client.complete(SYMPTOM_SYSTEM, user)


SYMPTOM_TEXT_SYSTEM = (
    "Eres un clinico de ejercicio femenino. Recibes sintomas escritos en texto libre y debes "
    "mapearlos SOLO a las opciones permitidas. Devuelve un unico JSON con esta forma: "
    '{"symptom_ids": ["..."], "severity": {"<id>": 1-10}, "avoid_patterns": ["..."], '
    '"guidance": "consejo breve", "absolute_contraindication": false}. '
    "symptom_ids SOLO de allowed_symptoms; avoid_patterns SOLO de allowed_patterns. "
    "Si el texto no coincide con nada, devuelve listas vacias. No inventes ids ni patrones. "
    "Marca absolute_contraindication=true solo con signos muy riesgosos (dilatacion, sangrado, "
    "contracciones regulares); en ese caso recomienda movilidad suave y consultar a un profesional."
)


def _pattern_vocabulary() -> list[str]:
    from syncfit_contracts import load_exercises, patterns_of

    seen: set[str] = set()
    for exercise in load_exercises():
        pattern = patterns_of(exercise)
        if pattern:
            seen.add(str(pattern))
    return sorted(seen)


def _allowed_symptoms(modality: str | None) -> list[dict]:
    from syncfit_contracts import load_symptoms

    allowed = []
    for symptom in load_symptoms():
        scope = str(symptom.get("modality", "ANY"))
        if modality and scope not in ("ANY", modality):
            continue
        allowed.append({"id": symptom["id"], "name": symptom.get("name", {})})
    return allowed


def _severity(value: Any) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    return int(round(max(0.0, min(10.0, number))))


def sanitize_symptom_analysis(
    raw: Any, allowed_ids: set[str], allowed_patterns: set[str]
) -> dict:
    """Keep only ids/patterns that exist, clamp severity and cap the guidance text."""
    if not isinstance(raw, dict):
        raw = {}
    ids: list[str] = []
    for item in raw.get("symptom_ids") or []:
        symptom_id = str(item)
        if symptom_id in allowed_ids and symptom_id not in ids:
            ids.append(symptom_id)
    raw_severity = raw.get("severity") if isinstance(raw.get("severity"), dict) else {}
    severity = {
        symptom_id: _severity(raw_severity.get(symptom_id))
        for symptom_id in ids
        if symptom_id in raw_severity
    }
    patterns: list[str] = []
    for item in raw.get("avoid_patterns") or []:
        pattern = str(item)
        if pattern in allowed_patterns and pattern not in patterns:
            patterns.append(pattern)
    guidance = raw.get("guidance")
    guidance = guidance.strip()[:600] if isinstance(guidance, str) else ""
    return {
        "symptom_ids": ids,
        "severity": severity,
        "avoid_patterns": patterns,
        "guidance": guidance,
        "absolute_contraindication": bool(raw.get("absolute_contraindication")),
    }


def interpret_symptom_text(
    text: str,
    language: str = "EN",
    modality: str | None = None,
    pain_level: int | None = None,
    client: Any | None = None,
) -> dict:
    """Turn free-text symptoms into validated catalog ids and movement patterns."""
    client = client or OpenCodeGoClient()
    allowed_symptoms = _allowed_symptoms(modality)
    allowed_patterns = _pattern_vocabulary()
    payload = {
        "language": language,
        "modality": modality,
        "pain_level": pain_level,
        "text": text,
        "allowed_symptoms": allowed_symptoms,
        "allowed_patterns": allowed_patterns,
    }
    raw = client.complete(SYMPTOM_TEXT_SYSTEM, json.dumps(payload, ensure_ascii=False))
    return sanitize_symptom_analysis(
        raw,
        {symptom["id"] for symptom in allowed_symptoms},
        set(allowed_patterns),
    )


__all__ = [
    "analyze_machine",
    "analyze_symptoms",
    "interpret_symptom_text",
    "sanitize_symptom_analysis",
]

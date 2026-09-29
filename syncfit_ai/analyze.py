"""AI analysis helpers: infer machine info and interpret symptoms from text."""

from __future__ import annotations

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


def analyze_machine(name: str, description: str | None = None, language: str = "EN", client: Any | None = None) -> dict:
    """Infer a machine's type, localized name/purpose, exercises and weight factor."""
    client = client or OpenCodeGoClient()
    user = f"language={language}\nname={name}\ndescription={description or ''}"
    return client.complete(MACHINE_SYSTEM, user)


def analyze_symptoms(symptoms: list[dict], language: str = "EN", client: Any | None = None) -> dict:
    client = client or OpenCodeGoClient()
    import json

    user = f"language={language}\nsymptoms={json.dumps(symptoms, ensure_ascii=False)}"
    return client.complete(SYMPTOM_SYSTEM, user)


__all__ = ["analyze_machine", "analyze_symptoms"]

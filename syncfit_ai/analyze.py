"""AI analysis helpers: infer machine info and interpret symptoms from text."""

from __future__ import annotations

from typing import Any

from .client import OpenCodeGoClient

MACHINE_SYSTEM = (
    "Eres un experto en equipamiento de gimnasio. Devuelve SOLO un objeto JSON con: "
    '{"inferred_type": "FREE_WEIGHT|MACHINE|SMITH|CABLE|BODYWEIGHT|ASSISTED|BAND|NONE", '
    '"purpose": "para que sirve, en tus palabras", '
    '"exercise_ids": ["movimientos que permite"], '
    '"weight_factor": number}. Basate en el nombre y descripcion; si solo hay nombre, inferí. '
    "Responde en el idioma indicado para purpose."
)

SYMPTOM_SYSTEM = (
    "Eres un clinico de ejercicio femenino. Recibe sintomas con intensidad 1-10 y notas libres. "
    "Devuelve SOLO JSON: {\"absolute_contraindication\": bool, "
    "\"guidance\": \"consejo breve\", \"avoid\": [\"tipos de ejercicio a evitar\"]}. "
    "Marca absolute_contraindication=true SOLO en casos muy riesgosos (p.ej. dilatacion, "
    "sangrado, contracciones regulares). Si es asi, recomienda lo mas suave (movilidad, "
    "estiramientos) sin dejar de estar activa."
)


def analyze_machine(name: str, description: str | None = None, language: str = "ES", client: Any | None = None) -> dict:
    client = client or OpenCodeGoClient()
    user = f"language={language}\nname={name}\ndescription={description or ''}"
    return client.complete(MACHINE_SYSTEM, user)


def analyze_symptoms(symptoms: list[dict], language: str = "ES", client: Any | None = None) -> dict:
    client = client or OpenCodeGoClient()
    import json

    user = f"language={language}\nsymptoms={json.dumps(symptoms, ensure_ascii=False)}"
    return client.complete(SYMPTOM_SYSTEM, user)


__all__ = ["analyze_machine", "analyze_symptoms"]

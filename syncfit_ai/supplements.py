"""Supplement recommendations from the shared catalog.

Deterministic and offline-friendly: filters the localized supplement catalog by
objective and modality, applies pregnancy safety and returns a validated
`SupplementAdvice`. The reasoning model can later enrich the reasons.
"""

from __future__ import annotations

from syncfit_contracts import (
    SupplementAdvice,
    SupplementAdviceItem,
    SupplementRequest,
    localize,
    supplements_for,
)

_OBJECTIVE_LABEL = {
    "STRENGTH": {"en": "strength", "es": "fuerza", "zh": "力量"},
    "HYPERTROPHY": {"en": "muscle gain", "es": "ganancia muscular", "zh": "增肌"},
    "FAT_LOSS": {"en": "fat loss", "es": "pérdida de grasa", "zh": "减脂"},
    "HEALTH": {"en": "general health", "es": "salud general", "zh": "整体健康"},
    "RECOVERY": {"en": "recovery", "es": "recuperación", "zh": "恢复"},
    "PERFORMANCE": {"en": "performance", "es": "rendimiento", "zh": "运动表现"},
    "GESTATIONAL_HEALTH": {
        "en": "gestational health",
        "es": "salud gestacional",
        "zh": "孕期健康",
    },
}

_REASON = {
    "SAFE": {
        "en": "Suitable for your context.",
        "es": "Adecuado para tu contexto.",
        "zh": "适合当前情况。",
    },
    "CAUTION": {
        "en": "Use with caution and confirm with a clinician.",
        "es": "Usar con precaución y confirmar con un clínico.",
        "zh": "谨慎使用，并咨询医生。",
    },
    "AVOID": {
        "en": "Not recommended in this context.",
        "es": "No recomendado en este contexto.",
        "zh": "此情况下不推荐。",
    },
}


def _value(item: object) -> str:
    return item.value if hasattr(item, "value") else str(item)


def _reason(safety: str, objective: str | None, language: str) -> dict[str, str]:
    base = dict(_REASON.get(safety, _REASON["SAFE"]))
    if objective and objective in _OBJECTIVE_LABEL:
        label = _OBJECTIVE_LABEL[objective]
        code = language.lower()
        suffix = label.get(code, label["en"])
        for key in base:
            base[key] = f"{base[key]} ({suffix})" if key == code or key == "en" else base[key]
    return base


def recommend_supplements(request: SupplementRequest) -> SupplementAdvice:
    """Build a supplement advice payload for the request context."""
    language = _value(request.language)
    modality = _value(request.modality)
    objective = _value(request.objective) if request.objective else None

    supplements = supplements_for(objective=objective, modality=modality)
    items: list[SupplementAdviceItem] = []
    for supplement in supplements:
        safety = (
            supplement.safety_pregnancy if modality == "GESTATIONAL" else supplement.safety_general
        )
        items.append(
            SupplementAdviceItem(
                supplement_id=supplement.id,
                name=supplement.name,
                category=supplement.category,
                safety=safety,
                dosage=supplement.dosage,
                macros=supplement.macros,
                reason=_reason(_value(safety), objective, language),
                image_url=supplement.image_url,
            )
        )
    return SupplementAdvice(
        language=language,
        modality=modality,
        objective=objective,
        items=items,
    )


__all__ = ["recommend_supplements"]

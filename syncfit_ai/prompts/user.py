"""Builds the user prompt from a reasoning request."""

from __future__ import annotations

import json

from ..domain import AuditRequest
from .system import RESPONSE_SCHEMA


def build_user_prompt(request: AuditRequest) -> str:
    """Serialize the telemetry, the deterministic decision and the routine."""
    core = request.core_result
    features = core.features

    payload = {
        "session_id": request.session_id,
        "telemetry": {
            "modality": features.modality.value,
            "day_or_week": features.day_or_week,
            "delta_temperature_c": features.delta_temperature_c,
            "rmssd_hrv_ms": features.rmssd_hrv_ms,
            "isometric_force_loss_pct": features.isometric_force_loss_pct,
        },
        "deterministic_decision": {
            "phase_inferred": core.phase_inferred.value,
            "fatigue_probability": round(core.fatigue_probability, 4),
            "fatigue_level": core.fatigue_level.value,
            "k_load_multiplier": core.k_load,
        },
        "programmed_routine": [exercise.as_dict() for exercise in request.programmed_routine],
    }

    return (
        "Process the following telemetry and produce the biomechanical adaptation.\n"
        "Return only the JSON object, echoing the deterministic phase and k_load.\n\n"
        f"Input:\n{json.dumps(payload, indent=2, ensure_ascii=False)}\n\n"
        f"Required JSON schema:\n{RESPONSE_SCHEMA}\n"
    )


__all__ = ["build_user_prompt"]

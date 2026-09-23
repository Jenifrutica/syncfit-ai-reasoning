"""Validation of the model output against the shared contract."""

from __future__ import annotations

from typing import Any

from syncfit_contracts import AIReasoningResponse


class SchemaValidationError(ValueError):
    """Raised when the model output does not match the contract."""


def validate_ai_response(payload: dict[str, Any]) -> AIReasoningResponse:
    """Validate a raw model payload against `AIReasoningResponse`."""
    try:
        return AIReasoningResponse.model_validate(payload)
    except Exception as exc:  # pydantic ValidationError and friends
        raise SchemaValidationError(str(exc)) from exc


__all__ = ["validate_ai_response", "SchemaValidationError"]

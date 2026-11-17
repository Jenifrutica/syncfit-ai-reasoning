"""Database-driven option parameters.

The backend loads the ``app_options`` rows (objectives with their training
scheme, labels...) and registers them here, so an objective added by the super
admin is used by the engines without a code change. Missing values fall back to
the built-in tables.
"""

from __future__ import annotations

from typing import Any

_SCHEME_KEYS = ("sets", "reps", "rest_compound", "rest_iso")
_objective_schemes: dict[str, dict[str, int]] = {}
_objective_labels: dict[str, dict[str, str]] = {}


def set_objectives(options: list[dict[str, Any]]) -> None:
    """Register objective options: ``[{"value", "labels", "meta"}, ...]``."""
    schemes: dict[str, dict[str, int]] = {}
    labels: dict[str, dict[str, str]] = {}
    for option in options:
        value = str(option.get("value") or "").upper()
        if not value:
            continue
        meta = option.get("meta") or {}
        scheme = {key: int(meta[key]) for key in _SCHEME_KEYS if isinstance(meta.get(key), (int, float))}
        if scheme:
            schemes[value] = scheme
        if option.get("labels"):
            labels[value] = {str(k).lower(): str(v) for k, v in option["labels"].items()}
    _objective_schemes.clear()
    _objective_schemes.update(schemes)
    _objective_labels.clear()
    _objective_labels.update(labels)


def objective_scheme(value: str) -> dict[str, int]:
    return dict(_objective_schemes.get(value, {}))


def objective_label(value: str) -> dict[str, str] | None:
    return _objective_labels.get(value)

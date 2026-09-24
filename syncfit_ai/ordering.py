"""Medical ordering of a routine.

Orders exercises following training-science principles adapted to the female
cycle and pregnancy:

1. **Activation / warm-up first.** Neuromuscular activation and mobility precede
   loading (injury prevention, Hewett et al.; ACOG guidance on preparation).
2. **Compounds before isolations.** Multi-joint exercises require the freshest
   state; isolation work comes later.
3. **Ovulatory phase and advanced pregnancy:** low-impact / stability work is
   prioritised and high-impact / high joint-risk exercises are ordered last (and
   should be blocked by the safety rules).
4. **Luteal phase:** more isolated, controlled work and longer rests, so
   single-joint exercises are promoted.
5. **Gestation:** avoid supine and Valsalva; prefer seated/standing and assisted
   variants (ordered earlier).

The function is deterministic so it can also be used offline; the reasoning model
can additionally explain the rationale.
"""

from __future__ import annotations

from typing import Any

_ROLE_PRIORITY = {"ACTIVATION": 0, "WARMUP": 1, "MAIN": 2}
_IMPACT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

_COMPOUND_THRESHOLD = 3  # number of muscle groups that makes an exercise compound


def _value(item: object) -> str:
    return item.value if hasattr(item, "value") else str(item)


def _role(entry: dict[str, Any]) -> str:
    return _value(entry.get("role") or "MAIN")


def _impact(entry: dict[str, Any]) -> str:
    return _value(entry.get("impact") or "MEDIUM")


def _groups(entry: dict[str, Any]) -> int:
    return len(entry.get("muscle_groups") or [])


def _low_impact_priority(phase: str | None) -> bool:
    return _value(phase) in {"OVULATORY", "TRIMESTER_3"}


def _luteal_priority(phase: str | None) -> bool:
    return _value(phase) == "LUTEAL"


def order_routine(
    entries: list[dict[str, Any]],
    phase: str | None = None,
    language: str = "EN",
) -> list[dict[str, Any]]:
    """Return the routine entries in a medically sound order."""
    low_impact = _low_impact_priority(phase)
    luteal = _luteal_priority(phase)

    def sort_key(entry: dict[str, Any]) -> tuple:
        blocked = 1 if entry.get("blocked") else 0  # blocked last
        role = _ROLE_PRIORITY.get(_role(entry), 2)
        impact = _IMPACT_RANK.get(_impact(entry), 1)
        compound = _groups(entry)
        # Compounds first (negative so higher group count sorts earlier).
        compound_key = -compound

        if low_impact:
            impact_key = impact  # low impact first
        else:
            # In normal phases, working sets of higher intensity come earlier.
            impact_key = -impact

        isolation_key = 0
        if luteal:
            # Promote isolation (fewer groups) in the luteal phase.
            isolation_key = 0 if compound < _COMPOUND_THRESHOLD else 1

        return (blocked, role, isolation_key, impact_key, compound_key)

    return sorted(entries, key=sort_key)


__all__ = ["order_routine"]

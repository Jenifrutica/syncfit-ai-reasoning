"""Medical ordering of a routine.

Orders exercises following the evidence on exercise sequencing, adapted to the
female cycle and pregnancy:

1. **Activation / warm-up first.** Mobility and neuromuscular activation precede
   loading (injury prevention, Hewett et al.; ACOG guidance on preparation).
2. **Bilateral multi-joint (compound) exercises next.** Strength gains are
   largest in the exercises performed while fresh. ACSM (2009) recommends
   multiple-joint before single-joint and large before small muscle groups; the
   meta-analysis by Nunes et al. (2020) found that starting with multi-joint
   exercises improves multi-joint strength (ES = 0.32, p = 0.034), while
   hypertrophy is similar either way (ES = 0.03, p = 0.862). Simão et al. (2012)
   reach the same conclusion: prioritise the exercise that matters most.
3. **Unilateral multi-joint work** (lunges, split squats, step-ups) after the
   bilateral compounds and before the accessories. No trial compares this exact
   position; it follows the compound → single-joint consensus plus the higher
   balance/stability demand, which is better placed before local fatigue.
4. **Accessories / single-joint last.** They are the least technically demanding
   and their fatigue does not compromise the main lifts.
5. **Ovulatory phase and third trimester:** low-impact work is prioritised
   (safety), so the impact rank is used as the first tiebreaker.
6. **Gestation:** avoid supine and Valsalva; the safety rules block those.

Blocked exercises always go last. Note that the luteal phase no longer inverts
the order: there is no evidence for promoting isolation work there, and it
contradicts the compound-first principle. Cycle adaptation stays in the load and
fatigue computation.

The function is deterministic so it can also be used offline; the reasoning model
can additionally explain the rationale.

References
----------
- American College of Sports Medicine (2009). Progression models in resistance
  training for healthy adults. *Med Sci Sports Exerc*, 41(3), 687-708.
- Nunes, J. P., et al. (2020). What influence does resistance exercise order
  have on muscular strength gains and muscle hypertrophy? A systematic review
  and meta-analysis. *Eur J Sport Sci*.
- Simão, R., et al. (2012). Exercise order in resistance training.
  *Sports Med*, 42(3), 251-265.
"""

from __future__ import annotations

from typing import Any

_ROLE_PRIORITY = {"ACTIVATION": 0, "WARMUP": 1, "MAIN": 2}
_IMPACT_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}

_COMPOUND_THRESHOLD = 3  # number of muscle groups that makes an exercise compound

# Multi-joint patterns performed one limb at a time. Add new catalog patterns here.
_UNILATERAL_PATTERNS = {"lunge", "step_up", "step-up", "split_squat", "single_leg", "single_arm"}


def _value(item: object) -> str:
    return item.value if hasattr(item, "value") else str(item)


def _role(entry: dict[str, Any]) -> str:
    return _value(entry.get("role") or "MAIN")


def _impact(entry: dict[str, Any]) -> str:
    return _value(entry.get("impact") or "MEDIUM")


def _groups(entry: dict[str, Any]) -> int:
    return len(entry.get("muscle_groups") or [])


def _is_compound(entry: dict[str, Any]) -> bool:
    """Explicit `compound` flag wins; fall back to the muscle-group count."""
    flag = entry.get("compound")
    if isinstance(flag, bool):
        return flag
    return _groups(entry) >= _COMPOUND_THRESHOLD


def _is_unilateral(entry: dict[str, Any]) -> bool:
    pattern = _value(entry.get("movement_pattern") or "").strip().lower()
    return pattern in _UNILATERAL_PATTERNS


def _tier(entry: dict[str, Any]) -> int:
    """0 bilateral compound · 1 unilateral multi-joint · 2 accessory / single-joint."""
    if not _is_compound(entry):
        return 2
    return 1 if _is_unilateral(entry) else 0


def _low_impact_priority(phase: str | None) -> bool:
    return _value(phase) in {"OVULATORY", "TRIMESTER_3"}


def order_routine(
    entries: list[dict[str, Any]],
    phase: str | None = None,
    language: str = "EN",
) -> list[dict[str, Any]]:
    """Return the routine entries in a medically sound order."""
    low_impact = _low_impact_priority(phase)

    def sort_key(entry: dict[str, Any]) -> tuple:
        blocked = 1 if entry.get("blocked") else 0  # blocked last
        role = _ROLE_PRIORITY.get(_role(entry), 2)
        tier = _tier(entry)
        # Only low-impact phases reorder by impact (LOW first); otherwise it is
        # a neutral tiebreaker and compounds always lead.
        impact_key = _IMPACT_RANK.get(_impact(entry), 1) if low_impact else 0
        # More muscle groups first inside a tier (large before small).
        return (blocked, role, tier, impact_key, -_groups(entry))

    return sorted(entries, key=sort_key)


__all__ = ["order_routine"]

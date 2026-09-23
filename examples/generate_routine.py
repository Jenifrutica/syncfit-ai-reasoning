"""Generate a routine by muscle group (offline or via OpenCode).

Usage:
    python examples/generate_routine.py --groups GLUTES,QUADRICEPS --language ES --offline
    python examples/generate_routine.py --groups UPPER_BODY --language ZH
    python examples/generate_routine.py --groups FULL_LEG --phase OVULATORY --offline
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from syncfit_ai import FakeClient, OpenCodeGoClient, RoutinePlanner  # noqa: E402
from syncfit_contracts import RoutineRequest  # noqa: E402
from syncfit_core import EngineResult  # noqa: E402
from syncfit_core.enums import FatigueLevel, InferredPhase, Modality  # noqa: E402
from syncfit_core.features import build_feature_vector  # noqa: E402


def core_result_for(phase: str | None) -> EngineResult | None:
    """Optionally build a synthetic core result so the safety rules apply."""
    if not phase:
        return None
    inferred = InferredPhase(phase)
    features = build_feature_vector(Modality.MENSTRUAL_CYCLE, 14, 0.42, 28.5, 12.8)
    k_load = 0.72 if inferred in (InferredPhase.OVULATORY, InferredPhase.TRIMESTER_3) else 0.9
    return EngineResult(
        phase_inferred=inferred,
        fatigue_probability=0.6,
        fatigue_level=FatigueLevel.MEDIUM,
        k_load=k_load,
        rmssd_hrv_ms=28.5,
        features=features,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a SyncFit routine by muscle group.")
    parser.add_argument("--groups", required=True, help="comma-separated muscle groups")
    parser.add_argument("--language", default="EN", choices=["EN", "ES", "ZH"])
    parser.add_argument("--per-group", type=int, default=2)
    parser.add_argument("--phase", default=None, help="simulate a core phase, e.g. OVULATORY")
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    request = RoutineRequest(
        muscle_groups=[g.strip() for g in args.groups.split(",") if g.strip()],
        language=args.language,
        exercises_per_group=args.per_group,
    )
    core_result = core_result_for(args.phase)

    if args.offline:
        planner = RoutinePlanner(FakeClient(response={}))
        result = planner.plan_offline(request, core_result)
    else:
        planner = RoutinePlanner(OpenCodeGoClient())
        result = planner.plan(request, core_result)

    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

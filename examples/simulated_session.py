"""Full-chain example: simulator -> core -> reasoning.

Simulates telemetry (standing in for the hardware), runs the deterministic core
engine and sends the decision to the reasoning kernel for the biomechanical
audit. Reproduces the situation the real device will trigger.

Usage:
    python examples/simulated_session.py                 # real OpenCode call
    python examples/simulated_session.py --offline       # deterministic FakeClient
    python examples/simulated_session.py --scenario high_risk
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from syncfit_ai import (  # noqa: E402
    AuditRequest,
    BiomechanicalAuditor,
    FakeClient,
    OpenCodeGoClient,
    ProgrammedExercise,
)
from syncfit_simulator import get_scenario, run_scenario, scenario_names  # noqa: E402

SESSION_ID = "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"

PROGRAMMED_ROUTINE = [
    ProgrammedExercise("Heavy back squat", series=4, reps=6, weight_kg=80.0),
    ProgrammedExercise("Plyometric box jumps", series=3, reps=8, weight_kg=0.0),
    ProgrammedExercise("Flat barbell bench press", series=4, reps=8, weight_kg=45.0),
]

# Offline canned model output. The deterministic rule engine corrects it.
FAKE_RESPONSE = {
    "schema_version": "1.0.0",
    "session_id": SESSION_ID,
    "phase_inferred": "LUTEAL",
    "fatigue_level": "LOW",
    "articular_risk_pct": 10.0,
    "k_load_multiplier": 1.05,
    "alerts": [],
    "adapted_routine": [],
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SyncFit Edge full chain with the simulator.")
    parser.add_argument("--scenario", default="high_risk", choices=scenario_names())
    parser.add_argument("--frames", type=int, default=2)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args(argv)

    # 1. Simulator generates telemetry and runs it through the core engine.
    harness_result = run_scenario(
        get_scenario(args.scenario), session_id=SESSION_ID, frames=args.frames
    )
    core_result = harness_result.final
    print(
        f"[simulator+core] scenario={args.scenario} phase={core_result.phase_inferred.value} "
        f"fatigue={core_result.fatigue_level.value} k_load={core_result.k_load:.4f}",
        file=sys.stderr,
    )

    # 2. Reasoning kernel audits the deterministic decision.
    request = AuditRequest(
        session_id=SESSION_ID,
        core_result=core_result,
        programmed_routine=PROGRAMMED_ROUTINE,
    )
    client = FakeClient(response=FAKE_RESPONSE) if args.offline else OpenCodeGoClient()
    prescription = BiomechanicalAuditor(client).audit_dict(request)
    print(json.dumps(prescription, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

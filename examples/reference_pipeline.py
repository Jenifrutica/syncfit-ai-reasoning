"""Reference pipeline: core (simulated data) -> OpenCode Go reasoning kernel.

Reproduces the test pipeline from the technical document: it simulates incoming
telemetry, runs the deterministic engine, sends the decision to the reasoning
kernel and prints the adapted prescription as strict JSON.

Usage:
    export REASONING_API_KEY="<your OpenCode Go key>"
    python examples/reference_pipeline.py

Add --offline to run with the deterministic FakeClient (no network, no key).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402

from syncfit_ai import (  # noqa: E402
    AuditRequest,
    BiomechanicalAuditor,
    FakeClient,
    OpenCodeGoClient,
    ProgrammedExercise,
)
from syncfit_core import SyncFitEngine, train_default_model  # noqa: E402

SESSION_ID = "3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d"

PROGRAMMED_ROUTINE = [
    ProgrammedExercise("Heavy back squat", series=4, reps=6, weight_kg=80.0),
    ProgrammedExercise("Plyometric box jumps", series=3, reps=8, weight_kg=0.0),
    ProgrammedExercise("Flat barbell bench press", series=4, reps=8, weight_kg=45.0),
]


def synthetic_ppg(seconds: int = 12, hr_bpm: int = 72, seed: int = 0) -> np.ndarray:
    fs = 100
    t = np.arange(fs * seconds) / fs
    rng = np.random.default_rng(seed)
    signal = np.sin(2 * np.pi * (hr_bpm / 60) * t) + 0.5 * np.sin(4 * np.pi * (hr_bpm / 60) * t)
    return signal + rng.normal(0, 0.01, signal.size)


FAKE_RESPONSE = {
    "schema_version": "1.0.0",
    "session_id": SESSION_ID,
    "phase_inferred": "OVULATORY",
    "fatigue_level": "HIGH",
    "articular_risk_pct": 78.0,
    "k_load_multiplier": 0.72,
    "alerts": [
        "Ovulatory phase detected: elevated ligament laxity and ACL injury risk.",
    ],
    "adapted_routine": [
        {
            "exercise_original": "Heavy back squat",
            "blocked": True,
            "block_reason": "High axial load during the ovulatory phase.",
            "exercise_substitute": "Guided goblet squat on a stable box",
            "series_adapted": 3,
            "reps_adapted": 10,
            "weight_suggested_kg": 16.0,
        }
    ],
}


def build_request() -> AuditRequest:
    model = train_default_model(n_samples=2000, seed=42)
    engine = SyncFitEngine(model, window_size=1024)
    engine.ingest(synthetic_ppg(seconds=12, hr_bpm=72))
    core_result = engine.evaluate(
        modality="MENSTRUAL_CYCLE",
        day_or_week=14,
        delta_temperature_c=0.42,
        isometric_force_loss_pct=12.8,
    )
    return AuditRequest(
        session_id=SESSION_ID,
        core_result=core_result,
        programmed_routine=PROGRAMMED_ROUTINE,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SyncFit Edge reasoning reference pipeline.")
    parser.add_argument("--offline", action="store_true", help="use FakeClient (no network)")
    args = parser.parse_args(argv)

    request = build_request()
    core = request.core_result
    print(
        f"[core] phase={core.phase_inferred.value} fatigue={core.fatigue_level.value} "
        f"k_load={core.k_load} rmssd={core.rmssd_hrv_ms:.1f} ms",
        file=sys.stderr,
    )

    if args.offline:
        client = FakeClient(response=FAKE_RESPONSE)
    else:
        client = OpenCodeGoClient()

    auditor = BiomechanicalAuditor(client)
    result = auditor.audit_dict(request)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

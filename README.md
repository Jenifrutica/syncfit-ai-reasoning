# SyncFit AI Reasoning

Cloud reasoning half of SyncFit Edge: the biomechanical audit kernel that turns the numeric output of [`syncfit-core`](https://github.com/Jenifrutica/syncfit-core) plus the programmed routine into a structured, adapted prescription.

## Purpose

Guarantee clinical reliability by **never** delegating the mathematical calculation to a generative model. The deterministic number (`k_load`) is computed in `syncfit-core`; this service only applies contextual biomechanical deduction and returns a strictly structured plan.

## What belongs here

- **LLM client** (`client/`): OpenCode Go through the OpenAI-compatible Python SDK, using **DeepSeek V4.1 Flash** (`base_url=https://opencode.ai/zen/go/v1`).
- **Prompts** (`prompts/`): the deterministic system prompt that defines the kernel as an analytical engine, not a chatbot, with temperature 0.1.
- **Strict output** (`schema/`): JSON Mode responses (`response_format={"type": "json_object"}`) validated against the schema in [`syncfit-contracts`](https://github.com/Jenifrutica/syncfit-contracts).
- **Biomechanical rules** (`rules/`): deterministic safety net that blocks high-impact / high joint-risk exercises in the ovulatory phase or advanced pregnancy, blocks supine exercises from week 16, and preserves the numeric `k_load`.
- **Orchestrator** (`auditor.py`): `BiomechanicalAuditor` ties prompts, client, rules and validation together.
- Reference pipeline that simulates telemetry, runs `syncfit-core` and prints the adapted JSON.

## What does NOT belong here

- DSP, filtering or RMSSD computation.
- Model training or `k_load` calculation (that is deterministic and belongs to `syncfit-core`).
- Hardware drivers, persistence or UI.

## Integration with the other repositories

- **`syncfit-core`** (dependency): supplies the deterministic `EngineResult` (phase, fatigue probability, fatigue level and `k_load`) that the kernel audits. `AuditRequest` wraps a `syncfit_core.EngineResult`.
- **`syncfit-contracts`** (dependency): provides the `AIReasoningResponse` model that every output is validated against.
- **`syncfit-simulator`** (optional, `[simulator]`): generates contract-valid telemetry and runs it through the core engine, so the reasoning kernel can be exercised with simulated data while the hardware is being built. See `examples/simulated_session.py`.

All are declared as git dependencies in `pyproject.toml`, so installing this package wires the whole chain.

## Configuration

OpenCode Go and OpenCode Zen are two OpenAI-compatible products that **share the
same account key**. The product is chosen by configuration, not by the key, so a
unified key works on either endpoint. DeepSeek V4.1 Flash is available on both.

| Variable | Default | Purpose |
|----------|---------|---------|
| `REASONING_API_KEY` | — | OpenCode account key (falls back to `OPENCODE_API_KEY`) |
| `REASONING_PRODUCT` | `go` | `go` or `zen`; selects the endpoint |
| `REASONING_AUTO_PRODUCT_FALLBACK` | `true` | If the product rejects the key, try the other product |
| `REASONING_BASE_URL` | product endpoint | Explicit endpoint override |
| `REASONING_MODEL` | `deepseek-v4.1-flash` | Model id |
| `REASONING_TEMPERATURE` | `0.1` | Deterministic temperature |
| `REASONING_TIMEOUT` | `60` | Request timeout (seconds) |

The key is read from (1) the environment, (2) a local `.env` file, in that order.
It is never stored in the repository.

```bash
cp .env.example .env
# edit .env and set REASONING_API_KEY=...
```

## Usage

```bash
pip install -e ".[dev]"
pytest
```

```python
from syncfit_ai import AuditRequest, BiomechanicalAuditor, OpenCodeGoClient, ProgrammedExercise

request = AuditRequest(
    session_id="3f1b2c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d",
    core_result=core_result,          # a syncfit_core.EngineResult
    programmed_routine=[
        ProgrammedExercise("Heavy back squat", series=4, reps=6, weight_kg=80.0),
    ],
)
auditor = BiomechanicalAuditor(OpenCodeGoClient())
prescription = auditor.audit(request)  # syncfit_contracts.AIReasoningResponse
```

### Reference pipeline

```bash
python examples/check_connection.py              # verify key, product and model
python examples/reference_pipeline.py            # real call to OpenCode
python examples/reference_pipeline.py --offline  # deterministic FakeClient, no network
# force a product:
REASONING_PRODUCT=zen python examples/check_connection.py
```

### Full chain with the simulator

Runs simulated telemetry through the simulator, the core engine and the reasoning
kernel (requires `pip install -e ".[simulator]"`):

```bash
python examples/simulated_session.py --scenario high_risk --offline  # no network
python examples/simulated_session.py --scenario high_risk            # real OpenCode call
```

> OpenCode requires the `x-opencode-session` header for routing; the client
> always sends one (generated when no session id is provided). Only a
> `response_format` rejection is retried; authentication and other errors are
> surfaced immediately.

### Routine generation by muscle group (i18n)

Builds a routine for one or more muscle groups (isolated, region or pattern),
localized in English (default), Spanish or Chinese. The model chooses exercise
ids from the shared catalog; the deterministic layer enriches each entry with a
localized name/description and a free-use `image_url`, and enforces the safety
rules.

```bash
python examples/generate_routine.py --groups GLUTES,QUADRICEPS --language ES --offline
python examples/generate_routine.py --groups UPPER_BODY --language ZH
python examples/generate_routine.py --groups FULL_LEG --phase OVULATORY   # blocks high impact
```

```python
from syncfit_ai import RoutinePlanner, OpenCodeGoClient
from syncfit_contracts import RoutineRequest

request = RoutineRequest(muscle_groups=["GLUTES", "QUADRICEPS"], language="ES")
routine = RoutinePlanner(OpenCodeGoClient()).plan(request, core_result)  # RoutineResponse
```

`RoutinePlanner.plan_offline(request, core_result)` builds the same shape without
any model call.

## Data Structures

| Structure | Complexity | Purpose |
|-----------|:----------:|---------|
| **Priority Queue** | O(log n) | Ordering audit jobs. |
| **LRU Cache** | O(1) amortized | Reusing identical audit results. |

These are recommended, not mandatory; the four mandatory structures of the project live in the backend.

## Repository layout

```
syncfit-ai-reasoning/
├── syncfit_ai/
│   ├── config.py          # env-driven configuration
│   ├── domain.py          # AuditRequest / ProgrammedExercise
│   ├── client/            # OpenCodeGoClient (real) + FakeClient (tests)
│   ├── prompts/           # system and user prompt builders
│   ├── schema/            # contract validation
│   ├── rules/             # deterministic biomechanical rule engine
│   ├── structures/        # PriorityQueue, LRUCache
│   └── auditor.py         # BiomechanicalAuditor
├── examples/reference_pipeline.py
├── tests/
├── pyproject.toml
└── README.md
```

## Stack

Python 3.11+, OpenAI Python SDK (OpenCode Go endpoint), Pydantic v2, `syncfit-contracts`, `syncfit-core`.

## Tasks

> **Language: Python 3.11+ (mandatory).**

### Requirements

- [x] Integrate DeepSeek V4.1 Flash via the OpenAI-compatible OpenCode Go SDK.
- [x] Implement the deterministic system prompt (temperature 0.1, analytical engine, not a chatbot).
- [x] Enforce JSON Mode and validate the output against `syncfit-contracts`.
- [x] Implement the biomechanical rule engine (block high-risk exercises in the ovulatory phase and advanced pregnancy; block supine exercises from week 16).
- [x] Preserve the numeric `k_load` computed by `syncfit-core` without alteration.
- [x] Implement the **Priority Queue** for audit jobs.
- [x] Implement the **LRU Cache** for repeated inferences.
- [x] Link with `syncfit-core` (EngineResult) and `syncfit-contracts` (AIReasoningResponse).
- [x] Add the reference test pipeline from the source document.
- [x] Write integration tests with schema validation.

## Machine analysis (localized)

`analyze_machine(name, description, language)` returns `inferred_type`, a localized
`name` and `purpose` (`{"en","es","zh"}`), the `exercise_ids` the machine covers and a
`weight_factor`, preferring the machine variant (hip-thrust-machine, smith-*, cable-*).
The admin may type in any language; the backend stores the localized
dicts (with a copy fallback when the AI is unavailable) and the routine builder uses
`exercise_ids` to prefer gym machines.

## Pattern-based prescription (evidence-informed)

The routine is built from **movement patterns**, not a flat exercise list:

- `build_prescription()` (deterministic core): one exercise per pattern (no
  duplicates), required-pattern coverage per muscle group, compounds first,
  contraindicated patterns excluded, gym-machine patterns prioritised.
- `RoutinePlanner.plan()` (**DeepSeek designs**): the local assessment + profile +
  gym machines + evidence go to `deepseek-v4-pro` (OpenCode Go), which returns the
  full routine (patterns, exercises, order, sets, reps, rest, rationale).
  `enforce_prescription()` then normalizes ids, enforces pattern coverage / no
  duplicate pattern / compounds-first / contraindications / machine-first and
  echoes `k_load` (never recomputed). Fallback: `build_prescription` when the AI
  is unavailable.

Required patterns (examples): GLUTES = hinge, lunge, hip_thrust, glute_kickback,
hip_abduction.

Equipment filter: exercises are restricted to the gym inventory
(`Exercise.required_equipment`): machines first, then free equipment
(dumbbell/barbell/smith/bench/cable), then bodyweight. `alternatives_for()` powers
the UI Change button (available options first). Contraindications come from the symptom catalog (`avoid_patterns`):
knee pain blocks lunge/squat; low-back pain blocks hinge/row.

Prescription rules (hypertrophy): 10-20 sets/muscle/week, 3-5 sets/exercise,
6-12 reps, rest 90-180 s compounds / 60-90 s isolation, progressive overload.

References (APA 7): Schoenfeld, B. J. (2017). *Science and Development of Muscle
Hypertrophy*.; Schoenfeld, Ogborn & Krieger (2016) frequency; Baz-Valle et al.
(2022) volume; Currier et al. (2023) rest intervals; Contreras et al. (2016) hip
thrust EMG; Plotkin et al. (2023) glute hypertrophy; ACOG (2020); Hewett et al.
(2007); Wojtys et al. (1998); Maniar et al. (2022); Mottola et al. (2018).

## Related repositories

- [`syncfit-contracts`](https://github.com/Jenifrutica/syncfit-contracts) — output schema (`AIReasoningResponse`).
- [`syncfit-core`](https://github.com/Jenifrutica/syncfit-core) — supplies phase, fatigue and `k_load`.
- [`syncfit-simulator`](https://github.com/Jenifrutica/syncfit-simulator) — simulated telemetry while the hardware is built.
- [`syncfit-backend`](https://github.com/Jenifrutica/syncfit-backend) — orchestrates this service.

All code, comments, documentation and commits in this repository are written in English.

## Context for a new session

**What it is.** Cloud reasoning kernel. Two paths: biomechanical audit of a
decision (`BiomechanicalAuditor`) and routine generation by muscle group
(`RoutinePlanner`), both with a deterministic safety layer.

**Stack.** Python 3.11+, OpenAI SDK pointed at **OpenCode Go**
(`https://opencode.ai/zen/go/v1`, model `deepseek-v4.1-flash`), Pydantic.

**Config.** `REASONING_API_KEY` (or `OPENCODE_API_KEY`), `REASONING_PRODUCT`
(`go`|`zen`, auto-fallback), model, temperature 0.1; reads `.env`.

**Layout.** `syncfit_ai/`: `client/` (OpenCodeGoClient, FakeClient), `prompts/`,
`schema/`, `rules/`, `routine.py` (RoutinePlanner, enrich, offline), `ordering.py`
(medical order: warmup/activation first, compounds first, low-impact in
ovulatory/advanced pregnancy, blocked last), `loads.py` (load variation from
k_load + energy), `supplements.py`, `auditor.py`.

**Examples.** `examples/check_connection.py`, `reference_pipeline.py`,
`simulated_session.py`, `generate_routine.py`.

**Rule.** Never compute `k_load` here; echo it from core. Output validated
against `AIReasoningResponse`/`RoutineResponse`. Tests offline via FakeClient.

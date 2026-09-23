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

Both are declared as git dependencies in `pyproject.toml`, so installing this package wires the whole chain.

## Configuration

| Variable | Default | Purpose |
|----------|---------|---------|
| `REASONING_API_KEY` | — | OpenCode Go API key (falls back to `OPENCODE_API_KEY`) |
| `REASONING_BASE_URL` | `https://opencode.ai/zen/go/v1` | OpenAI-compatible endpoint |
| `REASONING_MODEL` | `deepseek-v4.1-flash` | Model id |
| `REASONING_TEMPERATURE` | `0.1` | Deterministic temperature |
| `REASONING_TIMEOUT` | `60` | Request timeout (seconds) |

The API key is read from the environment and is never stored in the repository.

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
export REASONING_API_KEY="<your OpenCode Go key>"
python examples/reference_pipeline.py            # real call to OpenCode Go
python examples/reference_pipeline.py --offline  # deterministic FakeClient, no network
```

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

## Related repositories

- [`syncfit-contracts`](https://github.com/Jenifrutica/syncfit-contracts) — output schema (`AIReasoningResponse`).
- [`syncfit-core`](https://github.com/Jenifrutica/syncfit-core) — supplies phase, fatigue and `k_load`.
- [`syncfit-backend`](https://github.com/Jenifrutica/syncfit-backend) — orchestrates this service.

All code, comments, documentation and commits in this repository are written in English.

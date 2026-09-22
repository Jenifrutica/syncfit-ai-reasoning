# SyncFit AI Reasoning

Cloud reasoning half of SyncFit Edge: the biomechanical audit kernel that turns the numeric output of [`syncfit-core`](../syncfit-core) plus the programmed routine into a structured, adapted prescription.

## Purpose

Guarantee clinical reliability by **never** delegating the mathematical calculation to a generative model. The deterministic number (`k_load`) is computed in `syncfit-core`; this service only applies contextual biomechanical deduction and returns a strictly structured plan.

## What belongs here

- **LLM client** (`client/`): DeepSeek-V3 / DeepSeek-Coder through the OpenAI-compatible Python SDK (`base_url=https://api.deepseek.com`).
- **Prompts** (`prompts/`): the deterministic system prompt that defines the kernel as an analytical engine, not a chatbot, with temperature 0.1.
- **Strict output** (`schema/`): JSON Mode responses (`response_format={"type": "json_object"}`) validated against the schema in [`syncfit-contracts`](../syncfit-contracts).
- **Biomechanical rules** (`rules/`): block high-impact / high joint-risk exercises in the ovulatory phase or advanced pregnancy, block supine exercises from week 16, preserve the numeric `k_load`.
- **Local fallback** (`fallback/`): optional quantized deployment (DeepSeek-R1-Distill / Qwen 2.5) for strict biomedical privacy.
- Test pipeline that simulates incoming telemetry and prints the adapted JSON.

## What does NOT belong here

- DSP, filtering or RMSSD computation.
- Model training or `k_load` calculation (that is deterministic and belongs to `syncfit-core`).
- Hardware drivers, persistence or UI.

## Data Structures

| Structure | Complexity | Purpose |
|-----------|:----------:|---------|
| **Priority Queue** | O(log n) | Ordering audit jobs. |
| **LRU Cache** | O(1) amortized | Reusing identical audit results. |
| **Directed State Graph** | Graph traversal | Resolving which rules apply to the current phase or trimester. |

These are recommended, not mandatory; the four mandatory structures of the project live in the backend.

## Suggested structure

```
syncfit-ai-reasoning/
├── syncfit_ai/
│   ├── client/         # DeepSeek OpenAI-compatible client
│   ├── prompts/        # system prompt, user prompt builders
│   ├── schema/         # JSON Mode validation
│   ├── rules/          # biomechanical rule engine
│   └── fallback/       # local quantized model path
├── tests/
├── pyproject.toml
└── README.md
```

## Test pipeline

The source document defines a test script that simulates telemetry, applies the system prompt and emits the adapted prescription as strict JSON. It lives here as the reference integration test.

## Stack

Python 3.11+, OpenAI Python SDK (DeepSeek endpoint), Pydantic for validation.

## Tasks

> **Language: Python 3.11+ (mandatory).**

### Requirements

- [ ] Integrate DeepSeek-V3 / DeepSeek-Coder via the OpenAI-compatible Python SDK.
- [ ] Implement the deterministic system prompt (temperature 0.1, analytical engine, not a chatbot).
- [ ] Enforce JSON Mode and validate the output against `syncfit-contracts`.
- [ ] Implement the biomechanical rule engine (block high-risk exercises in the ovulatory phase and advanced pregnancy; block supine exercises from week 16).
- [ ] Preserve the numeric `k_load` computed by `syncfit-core` without alteration.
- [ ] Implement the **Priority Queue** for audit jobs.
- [ ] Implement the **LRU Cache** for repeated inferences.
- [ ] Implement the local quantized fallback (DeepSeek-R1-Distill / Qwen 2.5).
- [ ] Add the reference test pipeline from the source document.
- [ ] Write integration tests with schema validation.

## Related repositories

- [`syncfit-contracts`](../syncfit-contracts) — output schema.
- [`syncfit-core`](../syncfit-core) — supplies fatigue probability and `k_load`.
- [`syncfit-backend`](../syncfit-backend) — orchestrates this service.

All code, comments, documentation and commits in this repository are written in English.

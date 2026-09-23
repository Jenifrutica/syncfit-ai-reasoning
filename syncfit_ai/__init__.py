"""SyncFit AI Reasoning - cloud biomechanical audit kernel.

Turns the deterministic output of `syncfit-core` (phase, fatigue level, k_load)
plus the programmed routine into a structured, adapted prescription using
OpenCode Go (DeepSeek V4.1 Flash) in strict JSON mode. A deterministic rule
engine guarantees that the numeric decision is never altered by the model.
"""

from .auditor import BiomechanicalAuditor
from .client import FakeClient, OpenCodeGoClient, OpenCodeGoError, ReasoningClient
from .config import ReasoningConfig
from .domain import AuditRequest, ProgrammedExercise
from .routine import (
    DEFAULT_EXERCISES_PER_GROUP,
    RoutinePlanner,
    build_offline_routine,
    enrich_routine,
)
from .rules import enforce_rules, estimate_articular_risk, evaluate_exercise
from .schema import SchemaValidationError, validate_ai_response
from .structures import LRUCache, PriorityQueue

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "BiomechanicalAuditor",
    "ReasoningClient",
    "OpenCodeGoClient",
    "OpenCodeGoError",
    "FakeClient",
    "ReasoningConfig",
    "AuditRequest",
    "ProgrammedExercise",
    "RoutinePlanner",
    "build_offline_routine",
    "enrich_routine",
    "DEFAULT_EXERCISES_PER_GROUP",
    "enforce_rules",
    "estimate_articular_risk",
    "evaluate_exercise",
    "validate_ai_response",
    "SchemaValidationError",
    "LRUCache",
    "PriorityQueue",
]

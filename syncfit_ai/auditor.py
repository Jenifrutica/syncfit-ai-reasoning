"""Biomechanical auditor: the reasoning kernel orchestrator.

Flow: core decision + programmed routine -> prompt -> OpenCode Go -> deterministic
rule engine -> contract validation -> adapted prescription. Identical requests are
served from an LRU cache.
"""

from __future__ import annotations

import json
from typing import Any

from syncfit_contracts import AIReasoningResponse

from .client import ReasoningClient
from .domain import AuditRequest
from .prompts import build_system_prompt, build_user_prompt
from .rules import enforce_rules
from .schema import validate_ai_response
from .structures import LRUCache


class BiomechanicalAuditor:
    """Turns a deterministic core decision into an adapted prescription."""

    def __init__(
        self,
        client: ReasoningClient,
        cache_size: int = 128,
        use_cache: bool = True,
    ) -> None:
        self._client = client
        self._use_cache = use_cache
        self._cache: LRUCache[str, AIReasoningResponse] = LRUCache(capacity=cache_size)

    @property
    def cache(self) -> LRUCache[str, AIReasoningResponse]:
        return self._cache

    def _cache_key(self, request: AuditRequest) -> str:
        core = request.core_result
        return json.dumps(
            {
                "session_id": request.session_id,
                "phase": core.phase_inferred.value,
                "k_load": core.k_load,
                "fatigue": core.fatigue_level.value,
                "routine": [e.as_dict() for e in request.programmed_routine],
            },
            sort_keys=True,
        )

    def audit_dict(self, request: AuditRequest) -> dict[str, Any]:
        """Run the audit and return the validated payload as a dictionary."""
        return self.audit(request).model_dump()

    def audit(self, request: AuditRequest) -> AIReasoningResponse:
        """Run the audit and return a validated `AIReasoningResponse`."""
        key = self._cache_key(request)
        if self._use_cache:
            cached = self._cache.get(key)
            if cached is not None:
                return cached

        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(request)
        raw = self._client.complete(system_prompt, user_prompt, session_id=request.session_id)

        corrected = enforce_rules(request.core_result, raw, request)
        validated = validate_ai_response(corrected)

        if self._use_cache:
            self._cache.put(key, validated)
        return validated


__all__ = ["BiomechanicalAuditor"]

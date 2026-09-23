"""Deterministic in-memory client used by tests and offline demos."""

from __future__ import annotations

import copy
from typing import Any, Callable

Responder = Callable[[str, str, str | None], dict[str, Any]]


class FakeClient:
    """Returns a canned (or callback-generated) JSON object without any network."""

    def __init__(
        self,
        response: dict[str, Any] | None = None,
        responder: Responder | None = None,
    ) -> None:
        if response is None and responder is None:
            raise ValueError("provide either a response or a responder")
        self._response = response
        self._responder = responder
        self.calls: list[dict[str, Any]] = []

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        self.calls.append(
            {"system": system_prompt, "user": user_prompt, "session_id": session_id}
        )
        if self._responder is not None:
            return copy.deepcopy(self._responder(system_prompt, user_prompt, session_id))
        return copy.deepcopy(self._response or {})


__all__ = ["FakeClient"]

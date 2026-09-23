"""Reasoning client interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ReasoningClient(Protocol):
    """A client that returns a strict JSON object for a prompt pair."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Return the model output parsed as a JSON object."""
        ...


__all__ = ["ReasoningClient"]

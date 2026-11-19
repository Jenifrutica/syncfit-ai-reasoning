"""Reasoning client interface."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


class ReasoningProviderUnavailable(RuntimeError):
    """The provider could not return a usable response for this request."""


@runtime_checkable
class ReasoningClient(Protocol):
    """A client that returns a strict JSON object for a prompt pair."""

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        """Return parsed JSON or raise ReasoningProviderUnavailable for a provider failure."""
        ...


__all__ = ["ReasoningClient", "ReasoningProviderUnavailable"]

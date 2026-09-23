"""OpenCode Go client.

OpenCode Go exposes an OpenAI-compatible Chat Completions endpoint. The kernel
uses the DeepSeek V4.1 Flash model through it. Requests identify themselves with
a dedicated user agent and a stable session id, as OpenCode Go recommends.
"""

from __future__ import annotations

import json
from typing import Any

from ..config import ReasoningConfig


class OpenCodeGoError(RuntimeError):
    """Raised when the OpenCode Go call fails or returns invalid JSON."""


class OpenCodeGoClient:
    """Thin wrapper around the OpenAI-compatible OpenCode Go endpoint."""

    def __init__(self, config: ReasoningConfig | None = None, client: Any | None = None) -> None:
        self._config = config or ReasoningConfig.from_env()
        if not self._config.is_configured:
            raise OpenCodeGoError(
                "No API key configured. Set REASONING_API_KEY (or OPENCODE_API_KEY)."
            )
        self._client = client if client is not None else self._build_client()

    def _build_client(self) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise OpenCodeGoError(
                "The 'openai' package is required. Install it with `pip install openai`."
            ) from exc
        return OpenAI(
            api_key=self._config.api_key,
            base_url=self._config.base_url,
            timeout=self._config.timeout,
            default_headers={"User-Agent": self._config.user_agent},
        )

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        extra_headers = {"x-opencode-session": session_id} if session_id else None

        try:
            response = self._create(messages, extra_headers, json_mode=True)
        except Exception:
            # Some OpenAI-compatible endpoints reject response_format; retry
            # without it and rely on the deterministic rule engine + validation.
            response = self._create(messages, extra_headers, json_mode=False)

        content = response.choices[0].message.content
        if not content:
            raise OpenCodeGoError("Empty response from OpenCode Go.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenCodeGoError(f"Model did not return valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise OpenCodeGoError("Model returned JSON that is not an object.")
        return parsed

    def _create(
        self,
        messages: list[dict[str, str]],
        extra_headers: dict[str, str] | None,
        json_mode: bool,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": self._config.model,
            "messages": messages,
            "temperature": self._config.temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        return self._client.chat.completions.create(**kwargs)


__all__ = ["OpenCodeGoClient", "OpenCodeGoError"]

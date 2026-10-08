"""OpenCode Go / Zen client.

OpenCode Go and Zen share an account key. DeepSeek is called through Chat
Completions; transient failures can fall back to GPT-6 Luna through Responses.
Authentication failures may still try the other OpenCode product.

Requests identify themselves with a dedicated user agent and a stable session id,
as OpenCode recommends.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Callable

from ..config import ReasoningConfig

ClientFactory = Callable[[str], Any]


class OpenCodeGoError(RuntimeError):
    """Raised when the OpenCode call fails or returns invalid JSON."""


def _is_response_format_error(exc: Exception) -> bool:
    """True only when the endpoint rejected the response_format parameter."""
    message = str(exc).lower()
    return "response_format" in message or "text.format" in message


def _is_auth_error(exc: Exception) -> bool:
    """True for authentication/authorization failures (401/403)."""
    status = getattr(exc, "status_code", None)
    if status in (401, 403):
        return True
    name = type(exc).__name__
    return name in {"AuthenticationError", "PermissionDeniedError"}


def _is_transient_error(exc: Exception) -> bool:
    """True for provider/network failures that may succeed on another model."""
    status = getattr(exc, "status_code", None)
    if status in {408, 409, 425, 429} or (isinstance(status, int) and status >= 500):
        return True
    return isinstance(exc, (TimeoutError, ConnectionError)) or type(exc).__name__ in {
        "APIConnectionError",
        "APITimeoutError",
        "ConnectError",
        "ConnectTimeout",
        "PoolTimeout",
        "ReadTimeout",
        "WriteTimeout",
    }


class OpenCodeGoClient:
    """Thin wrapper around the OpenAI-compatible OpenCode endpoint."""

    def __init__(
        self,
        config: ReasoningConfig | None = None,
        client: Any | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._config = config or ReasoningConfig.from_env()
        if not self._config.is_configured:
            raise OpenCodeGoError(
                "No API key configured. Set REASONING_API_KEY (or OPENCODE_API_KEY)."
            )
        self._client = client
        self._client_factory = client_factory
        self._clients: dict[str, Any] = {}
        self.last_product_base_url: str | None = None
        self.last_model: str | None = None

    def _get_client(self, base_url: str) -> Any:
        if self._client is not None:
            return self._client
        if base_url in self._clients:
            return self._clients[base_url]
        if self._client_factory is not None:
            built = self._client_factory(base_url)
        else:
            built = self._build_client(base_url)
        self._clients[base_url] = built
        return built

    def _build_client(self, base_url: str) -> Any:
        try:
            from openai import OpenAI
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise OpenCodeGoError(
                "The 'openai' package is required. Install it with `pip install openai`."
            ) from exc
        return OpenAI(
            api_key=self._config.api_key,
            base_url=base_url,
            timeout=self._config.timeout,
            default_headers={"User-Agent": self._config.user_agent},
        )

    def _candidate_base_urls(self) -> list[str]:
        urls = [self._config.base_url]
        alternate = self._config.alternate_base_url
        if self._config.auto_product_fallback and alternate:
            urls.append(alternate)
        return urls

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
        # OpenCode requires a stable session id for routing and caching.
        extra_headers = {"x-opencode-session": session_id or str(uuid.uuid4())}

        last_error: Exception | None = None
        self.last_model = None
        candidates = self._candidate_base_urls()
        for index, base_url in enumerate(candidates):
            try:
                payload = self._complete_on(base_url, messages, extra_headers)
                self.last_product_base_url = base_url
                self.last_model = self._config.model
                return payload
            except Exception as exc:  # noqa: BLE001 - re-raised below if no fallback
                last_error = exc
                if _is_auth_error(exc) and index < len(candidates) - 1:
                    continue  # try the other product
                fallback_model = self._config.fallback_model
                if (
                    _is_transient_error(exc)
                    and fallback_model
                    and fallback_model != self._config.model
                ):
                    try:
                        payload = self._complete_with_responses(
                            base_url, fallback_model, messages, extra_headers
                        )
                    except Exception as fallback_exc:  # noqa: BLE001 - planner uses deterministic fallback
                        raise OpenCodeGoError(
                            f"Primary model {self._config.model} and fallback model "
                            f"{fallback_model} both failed."
                        ) from fallback_exc
                    self.last_product_base_url = base_url
                    self.last_model = fallback_model
                    return payload
                raise
        raise last_error if last_error else OpenCodeGoError("No endpoint available.")

    def _complete_on(
        self,
        base_url: str,
        messages: list[dict[str, str]],
        extra_headers: dict[str, str],
    ) -> dict[str, Any]:
        client = self._get_client(base_url)
        try:
            response = self._create(
                client, messages, extra_headers, json_mode=True, model=self._config.model
            )
        except Exception as exc:
            # Only retry without response_format when that parameter is the cause.
            if not _is_response_format_error(exc):
                raise
            response = self._create(
                client, messages, extra_headers, json_mode=False, model=self._config.model
            )

        content = response.choices[0].message.content
        return self._parse_json_object(content)

    def _complete_with_responses(
        self,
        base_url: str,
        model: str,
        messages: list[dict[str, str]],
        extra_headers: dict[str, str],
    ) -> dict[str, Any]:
        client = self._get_client(base_url)
        try:
            response = client.responses.create(
                model=model,
                instructions=messages[0]["content"],
                input=messages[1]["content"],
                text={"format": {"type": "json_object"}},
                extra_headers=extra_headers,
            )
        except Exception as exc:
            if not _is_response_format_error(exc):
                raise
            response = client.responses.create(
                model=model,
                instructions=messages[0]["content"],
                input=messages[1]["content"],
                extra_headers=extra_headers,
            )
        return self._parse_json_object(getattr(response, "output_text", None))

    @staticmethod
    def _parse_json_object(content: str | None) -> dict[str, Any]:
        if not content:
            raise OpenCodeGoError("Empty response from OpenCode.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise OpenCodeGoError(f"Model did not return valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise OpenCodeGoError("Model returned JSON that is not an object.")
        return parsed

    def _create(
        self,
        client: Any,
        messages: list[dict[str, str]],
        extra_headers: dict[str, str],
        json_mode: bool,
        model: str,
    ) -> Any:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": self._config.temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        if extra_headers:
            kwargs["extra_headers"] = extra_headers
        return client.chat.completions.create(**kwargs)


__all__ = ["OpenCodeGoClient", "OpenCodeGoError", "ClientFactory"]

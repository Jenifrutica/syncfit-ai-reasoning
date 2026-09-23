"""Runtime configuration for the reasoning kernel.

The kernel targets OpenCode Go (an OpenAI-compatible gateway) and uses the
DeepSeek V4.1 Flash model by default. Everything is configurable by environment
variable so the API key is never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

DEFAULT_BASE_URL = "https://opencode.ai/zen/go/v1"
DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 60.0
DEFAULT_USER_AGENT = "syncfit-ai-reasoning/0.1.0"

API_KEY_ENV_VARS = ("REASONING_API_KEY", "OPENCODE_API_KEY")


@dataclass(frozen=True)
class ReasoningConfig:
    """Immutable configuration for the reasoning client."""

    api_key: str | None = None
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    timeout: float = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ReasoningConfig":
        source = os.environ if env is None else env
        api_key = next(
            (source[name] for name in API_KEY_ENV_VARS if source.get(name)),
            None,
        )
        return cls(
            api_key=api_key,
            base_url=source.get("REASONING_BASE_URL", DEFAULT_BASE_URL),
            model=source.get("REASONING_MODEL", DEFAULT_MODEL),
            temperature=float(source.get("REASONING_TEMPERATURE", DEFAULT_TEMPERATURE)),
            timeout=float(source.get("REASONING_TIMEOUT", DEFAULT_TIMEOUT)),
            user_agent=source.get("REASONING_USER_AGENT", DEFAULT_USER_AGENT),
        )


__all__ = [
    "ReasoningConfig",
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "API_KEY_ENV_VARS",
]

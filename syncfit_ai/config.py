"""Runtime configuration for the reasoning kernel.

OpenCode Go and OpenCode Zen use the same account key. DeepSeek uses Chat
Completions; GPT-6 Luna is the configured outage fallback and uses Responses.

Everything is configurable by environment variable (or a local `.env`); the API
key is never hardcoded.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

PRODUCT_BASE_URLS: dict[str, str] = {
    "go": "https://opencode.ai/zen/go/v1",
    "zen": "https://opencode.ai/zen/v1",
}
PRODUCT_ALIASES: dict[str, str] = {
    "go": "go",
    "opencode-go": "go",
    "zen": "zen",
    "opencode": "zen",
}

DEFAULT_PRODUCT = "go"
DEFAULT_MODEL = "deepseek-v4-pro"
DEFAULT_FALLBACK_MODEL = "gpt-6-luna"
DEFAULT_TEMPERATURE = 0.25
DEFAULT_TIMEOUT = 120.0
DEFAULT_USER_AGENT = "syncfit-ai-reasoning/0.1.0"

API_KEY_ENV_VARS = ("REASONING_API_KEY", "OPENCODE_API_KEY")


def _load_dotenv() -> None:
    """Load the nearest `.env` file without overriding real environment vars."""
    cwd = Path.cwd()
    for directory in [cwd, *cwd.parents]:
        env_file = directory / ".env"
        if not env_file.is_file():
            continue
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if len(value) >= 2 and value[0] in {"'", '"'} and value[-1] == value[0]:
                value = value[1:-1]
            os.environ.setdefault(key, value)
        return


def normalize_product(product: str) -> str:
    """Map a product name or alias to 'go' or 'zen'."""
    return PRODUCT_ALIASES.get(product.strip().lower(), DEFAULT_PRODUCT)


@dataclass(frozen=True)
class ReasoningConfig:
    """Immutable configuration for the reasoning client."""

    api_key: str | None = None
    product: str = DEFAULT_PRODUCT
    base_url: str = PRODUCT_BASE_URLS[DEFAULT_PRODUCT]
    model: str = DEFAULT_MODEL
    fallback_model: str | None = DEFAULT_FALLBACK_MODEL
    temperature: float = DEFAULT_TEMPERATURE
    timeout: float = DEFAULT_TIMEOUT
    user_agent: str = DEFAULT_USER_AGENT
    auto_product_fallback: bool = True

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    @property
    def alternate_base_url(self) -> str | None:
        """The other product's endpoint, used when fallback is enabled."""
        other = "zen" if self.product == "go" else "go"
        alternate = PRODUCT_BASE_URLS[other]
        return None if alternate == self.base_url else alternate

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "ReasoningConfig":
        if env is None:
            _load_dotenv()
            source: Mapping[str, str] = os.environ
        else:
            source = env

        api_key = next(
            (source[name] for name in API_KEY_ENV_VARS if source.get(name)),
            None,
        )
        product = normalize_product(source.get("REASONING_PRODUCT", DEFAULT_PRODUCT))
        explicit_base_url = source.get("REASONING_BASE_URL")
        base_url = explicit_base_url or PRODUCT_BASE_URLS[product]
        auto_fallback = source.get(
            "REASONING_AUTO_PRODUCT_FALLBACK", "true"
        ).strip().lower() in {"1", "true", "yes", "on"}

        return cls(
            api_key=api_key,
            product=product,
            base_url=base_url,
            model=source.get("REASONING_MODEL", DEFAULT_MODEL),
            fallback_model=(
                source.get("REASONING_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL).strip()
                or None
            ),
            temperature=float(source.get("REASONING_TEMPERATURE", DEFAULT_TEMPERATURE)),
            timeout=float(source.get("REASONING_TIMEOUT", DEFAULT_TIMEOUT)),
            user_agent=source.get("REASONING_USER_AGENT", DEFAULT_USER_AGENT),
            auto_product_fallback=auto_fallback,
        )


__all__ = [
    "ReasoningConfig",
    "PRODUCT_BASE_URLS",
    "PRODUCT_ALIASES",
    "DEFAULT_PRODUCT",
    "DEFAULT_MODEL",
    "DEFAULT_FALLBACK_MODEL",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT",
    "DEFAULT_USER_AGENT",
    "API_KEY_ENV_VARS",
    "normalize_product",
]

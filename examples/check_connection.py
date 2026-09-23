"""Connectivity check for OpenCode (Go / Zen).

Verifies that the configured API key, product and model work before running the
full pipeline. OpenCode Go and Zen share the account key; the client tries the
configured product and automatically falls back to the other when the endpoint
rejects the key.

Never exposes the key.

Usage:
    export REASONING_API_KEY="<your OpenCode key>"
    python examples/check_connection.py
    # or force a product:
    REASONING_PRODUCT=zen python examples/check_connection.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from syncfit_ai import OpenCodeGoClient, OpenCodeGoError  # noqa: E402
from syncfit_ai.config import ReasoningConfig  # noqa: E402


def main() -> int:
    config = ReasoningConfig.from_env()
    if not config.is_configured:
        print("ERROR: no API key. Set REASONING_API_KEY (or OPENCODE_API_KEY) in the")
        print("environment or in a .env file.")
        return 2

    print(f"product  : {config.product}")
    print(f"base_url : {config.base_url}")
    print(f"model    : {config.model}")
    print(f"fallback : {config.auto_product_fallback} (other: {config.alternate_base_url})")
    print(f"api_key  : {'set' if config.api_key else 'missing'} (value hidden)")

    try:
        client = OpenCodeGoClient(config)
        result = client.complete(
            "You are a health check. Reply with a JSON object only.",
            'Return exactly this JSON: {"ok": true}',
            session_id="syncfit-healthcheck",
        )
    except OpenCodeGoError as exc:
        print(f"FAILED: {exc}")
        return 1
    except Exception as exc:  # surface auth/network errors clearly
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1

    used = client.last_product_base_url or config.base_url
    print(f"OK: key accepted. Response: {result}")
    print(f"endpoint that worked: {used}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

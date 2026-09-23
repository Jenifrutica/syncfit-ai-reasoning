"""Connectivity check for OpenCode Go.

Verifies that the configured API key, endpoint and model work before running the
full pipeline. Prints a clear result and never exposes the key.

Usage:
    export REASONING_API_KEY="<your OpenCode Go key>"
    python examples/check_connection.py
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
        print("ERROR: no API key. Set REASONING_API_KEY (or OPENCODE_API_KEY).")
        return 2

    print(f"base_url : {config.base_url}")
    print(f"model    : {config.model}")
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

    print(f"OK: endpoint reachable and key accepted. Response: {result}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

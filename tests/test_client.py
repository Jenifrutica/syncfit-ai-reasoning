import json

import pytest

from syncfit_ai.client import OpenCodeGoClient, OpenCodeGoError
from syncfit_ai.config import ReasoningConfig


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content, fail_json_mode=False):
        self.content = content
        self.fail_json_mode = fail_json_mode
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_json_mode and "response_format" in kwargs:
            raise RuntimeError("response_format not supported")
        return _Response(self.content)


class _Chat:
    def __init__(self, completions):
        self.completions = completions


class _FakeOpenAI:
    def __init__(self, completions):
        self.chat = _Chat(completions)


def make_client(content, fail_json_mode=False):
    completions = _Completions(content, fail_json_mode=fail_json_mode)
    config = ReasoningConfig(api_key="test-key")
    return OpenCodeGoClient(config=config, client=_FakeOpenAI(completions)), completions


def test_complete_parses_json():
    payload = {"phase_inferred": "OVULATORY", "k_load_multiplier": 0.72}
    client, completions = make_client(json.dumps(payload))
    result = client.complete("system", "user", session_id="sess-1")
    assert result == payload
    call = completions.calls[0]
    assert call["response_format"] == {"type": "json_object"}
    assert call["model"] == "deepseek-v4.1-flash"
    assert call["temperature"] == 0.1
    assert call["extra_headers"]["x-opencode-session"] == "sess-1"


def test_complete_retries_without_json_mode():
    payload = {"phase_inferred": "LUTEAL"}
    client, completions = make_client(json.dumps(payload), fail_json_mode=True)
    result = client.complete("system", "user")
    assert result == payload
    assert len(completions.calls) == 2
    assert "response_format" not in completions.calls[1]


def test_complete_invalid_json_raises():
    client, _ = make_client("not json at all")
    with pytest.raises(OpenCodeGoError):
        client.complete("system", "user")


def test_auth_error_is_not_swallowed():
    completions = _Completions("{}", fail_json_mode=False)
    completions.create = lambda **kwargs: (_ for _ in ()).throw(
        RuntimeError("Invalid API key")
    )
    client = OpenCodeGoClient(
        config=ReasoningConfig(api_key="bad"), client=_FakeOpenAI(completions)
    )
    with pytest.raises(RuntimeError, match="Invalid API key"):
        client.complete("system", "user")


def test_session_id_is_generated_when_missing():
    client, completions = make_client(json.dumps({"ok": True}))
    client.complete("system", "user")
    session = completions.calls[0]["extra_headers"]["x-opencode-session"]
    assert isinstance(session, str) and len(session) >= 32


def test_missing_api_key_raises():
    with pytest.raises(OpenCodeGoError):
        OpenCodeGoClient(config=ReasoningConfig(api_key=None))

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


class _ResponsesResult:
    def __init__(self, output_text):
        self.output_text = output_text


class _Responses:
    def __init__(self, output_text):
        self.output_text = output_text
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _ResponsesResult(self.output_text)


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
    def __init__(self, completions, responses=None):
        self.chat = _Chat(completions)
        self.responses = responses or _Responses("{}")


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
    assert call["model"] == "deepseek-v4-pro"
    assert call["temperature"] == 0.25
    assert call["extra_headers"]["x-opencode-session"] == "sess-1"


def test_complete_retries_without_json_mode():
    payload = {"phase_inferred": "LUTEAL"}
    client, completions = make_client(json.dumps(payload), fail_json_mode=True)
    result = client.complete("system", "user")
    assert result == payload
    assert len(completions.calls) == 2
    assert "response_format" not in completions.calls[1]


class _HttpError(Exception):
    def __init__(self, status_code):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code


def test_transient_primary_failure_uses_gpt6_responses_fallback():
    completions = _Completions("unused")
    completions.create = lambda **kwargs: (_ for _ in ()).throw(_HttpError(503))
    responses = _Responses('{"routine": []}')
    fake = _FakeOpenAI(completions, responses)
    client = OpenCodeGoClient(
        config=ReasoningConfig(api_key="test-key"), client=fake
    )

    result = client.complete("system instructions", "routine request", session_id="sess-2")

    assert result == {"routine": []}
    assert responses.calls[0]["model"] == "gpt-6-luna"
    assert responses.calls[0]["instructions"] == "system instructions"
    assert responses.calls[0]["input"] == "routine request"
    assert responses.calls[0]["text"] == {"format": {"type": "json_object"}}
    assert responses.calls[0]["extra_headers"]["x-opencode-session"] == "sess-2"
    assert client.last_model == "gpt-6-luna"


def test_non_transient_primary_failure_does_not_use_fallback():
    completions = _Completions("unused")
    completions.create = lambda **kwargs: (_ for _ in ()).throw(_HttpError(400))
    responses = _Responses('{"should_not_be_used": true}')
    client = OpenCodeGoClient(
        config=ReasoningConfig(api_key="test-key"),
        client=_FakeOpenAI(completions, responses),
    )

    with pytest.raises(_HttpError):
        client.complete("system", "user")
    assert responses.calls == []


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


class _AuthError(Exception):
    def __init__(self, message: str = "Unauthorized") -> None:
        super().__init__(message)
        self.status_code = 401


def make_factory(json_content, fail_urls):
    used = []

    def factory(base_url):
        used.append(base_url)
        completions = _Completions(json_content)
        if base_url in fail_urls:
            completions.create = lambda **kwargs: (_ for _ in ()).throw(_AuthError())
        return _FakeOpenAI(completions)

    return factory, used


def test_product_fallback_on_auth_error():
    from syncfit_ai.config import PRODUCT_BASE_URLS

    factory, used = make_factory(json.dumps({"ok": True}), {PRODUCT_BASE_URLS["go"]})
    client = OpenCodeGoClient(config=ReasoningConfig(api_key="k"), client_factory=factory)
    result = client.complete("system", "user")
    assert result == {"ok": True}
    assert used == [PRODUCT_BASE_URLS["go"], PRODUCT_BASE_URLS["zen"]]
    assert client.last_product_base_url == PRODUCT_BASE_URLS["zen"]


def test_no_fallback_when_disabled():
    from syncfit_ai.config import PRODUCT_BASE_URLS

    factory, used = make_factory(json.dumps({"ok": True}), {PRODUCT_BASE_URLS["go"]})
    config = ReasoningConfig(api_key="k", auto_product_fallback=False)
    client = OpenCodeGoClient(config=config, client_factory=factory)
    with pytest.raises(_AuthError):
        client.complete("system", "user")
    assert used == [PRODUCT_BASE_URLS["go"]]

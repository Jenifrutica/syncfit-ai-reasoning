from syncfit_ai.config import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    ReasoningConfig,
)


def test_defaults():
    config = ReasoningConfig()
    assert config.base_url == DEFAULT_BASE_URL
    assert config.model == DEFAULT_MODEL
    assert config.temperature == 0.1
    assert config.is_configured is False


def test_from_env_reads_api_key():
    config = ReasoningConfig.from_env(
        {"REASONING_API_KEY": "secret", "REASONING_MODEL": "deepseek-v4-pro"}
    )
    assert config.api_key == "secret"
    assert config.model == "deepseek-v4-pro"
    assert config.is_configured is True


def test_from_env_falls_back_to_opencode_key():
    config = ReasoningConfig.from_env({"OPENCODE_API_KEY": "go-key"})
    assert config.api_key == "go-key"


def test_from_env_defaults_without_keys():
    config = ReasoningConfig.from_env({})
    assert config.api_key is None
    assert config.base_url == DEFAULT_BASE_URL

from pathlib import Path

from syncfit_ai.config import (
    DEFAULT_MODEL,
    PRODUCT_BASE_URLS,
    ReasoningConfig,
    normalize_product,
)


def test_defaults():
    config = ReasoningConfig()
    assert config.product == "go"
    assert config.base_url == PRODUCT_BASE_URLS["go"]
    assert config.model == DEFAULT_MODEL
    assert config.temperature == 0.25
    assert config.is_configured is False
    assert config.alternate_base_url == PRODUCT_BASE_URLS["zen"]


def test_from_env_reads_api_key():
    config = ReasoningConfig.from_env(
        {"REASONING_API_KEY": "secret", "REASONING_MODEL": "deepseek-v4-pro"}
    )
    assert config.api_key == "secret"
    assert config.model == "deepseek-v4-pro"
    assert config.is_configured is True


def test_from_env_falls_back_to_opencode_key():
    assert ReasoningConfig.from_env({"OPENCODE_API_KEY": "go-key"}).api_key == "go-key"


def test_product_selects_endpoint():
    go = ReasoningConfig.from_env({"REASONING_PRODUCT": "go"})
    zen = ReasoningConfig.from_env({"REASONING_PRODUCT": "zen"})
    assert go.base_url == PRODUCT_BASE_URLS["go"]
    assert zen.base_url == PRODUCT_BASE_URLS["zen"]
    assert go.alternate_base_url == PRODUCT_BASE_URLS["zen"]
    assert zen.alternate_base_url == PRODUCT_BASE_URLS["go"]


def test_product_aliases():
    assert normalize_product("opencode-go") == "go"
    assert normalize_product("opencode") == "zen"
    assert normalize_product("ZEN") == "zen"
    assert normalize_product("unknown") == "go"


def test_explicit_base_url_overrides_product():
    config = ReasoningConfig.from_env(
        {"REASONING_PRODUCT": "zen", "REASONING_BASE_URL": "https://example.test/v1"}
    )
    assert config.base_url == "https://example.test/v1"


def test_auto_fallback_flag():
    assert ReasoningConfig.from_env({}).auto_product_fallback is True
    assert (
        ReasoningConfig.from_env({"REASONING_AUTO_PRODUCT_FALLBACK": "false"})
        .auto_product_fallback
        is False
    )


def test_dotenv_is_loaded(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("REASONING_API_KEY", raising=False)
    (tmp_path / ".env").write_text(
        "# comment\nREASONING_API_KEY=from-dotenv\nREASONING_PRODUCT=zen\n",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    config = ReasoningConfig.from_env()
    assert config.api_key == "from-dotenv"
    assert config.product == "zen"
    assert config.base_url == PRODUCT_BASE_URLS["zen"]


def test_real_env_wins_over_dotenv(monkeypatch, tmp_path: Path):
    (tmp_path / ".env").write_text("REASONING_API_KEY=from-dotenv\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("REASONING_API_KEY", "from-env")
    assert ReasoningConfig.from_env().api_key == "from-env"

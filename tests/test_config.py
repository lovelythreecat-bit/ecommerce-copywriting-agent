import pytest

from ecommerce_copy_agent.config import ModelConfig, load_model_config
from ecommerce_copy_agent.errors import ConfigurationError


def test_explicit_values_override_environment(monkeypatch):
    monkeypatch.setenv("COPY_AGENT_BASE_URL", "https://env.example/v1")
    monkeypatch.setenv("COPY_AGENT_API_KEY", "env-secret")
    monkeypatch.setenv("COPY_AGENT_MODEL", "env-model")
    monkeypatch.setenv("COPY_AGENT_SUPPORTS_IMAGES", "false")
    monkeypatch.setenv("COPY_AGENT_TIMEOUT_SECONDS", "9")
    config = load_model_config({
        "base_url": "https://explicit.example/v1", "api_key": "explicit-secret",
        "model": "explicit-model", "supports_images": True, "timeout_seconds": 12,
    })
    assert config.base_url == "https://explicit.example/v1"
    assert config.api_key.get_secret_value() == "explicit-secret"
    assert config.model == "explicit-model"
    assert config.supports_images is True
    assert config.timeout_seconds == 12
    assert "explicit-secret" not in repr(config)


@pytest.mark.parametrize("value", ["maybe", "1", ""])
def test_invalid_environment_boolean_rejected(monkeypatch, value):
    monkeypatch.setenv("COPY_AGENT_SUPPORTS_IMAGES", value)
    with pytest.raises(ConfigurationError):
        load_model_config({"base_url": "https://x.test/v1", "api_key": "test", "model": "m"})


@pytest.mark.parametrize("field,value", [
    ("api_key", ""), ("base_url", "ftp://x.test/v1"),
    ("base_url", "https://user:password@x.test/v1"), ("timeout_seconds", 0),
    ("base_url", "https://@x.test/v1"),
    ("base_url", "https://x.test/v1?api_key=embedded"),
    ("base_url", "https://relay.test:bad/v1"),
    ("base_url", "https://relay.test:99999/v1"),
    ("provider", "other"),
])
def test_invalid_configuration_rejected(field, value):
    values = {"base_url": "https://x.test/v1", "api_key": "test", "model": "m", field: value}
    with pytest.raises(ConfigurationError):
        load_model_config(values)


@pytest.mark.parametrize("base_url", [
    pytest.param("https://relay.test/private-endpoint/\nv1", id="embedded-newline"),
    pytest.param("https://relay.test/private-endpoint/\tv1", id="embedded-tab"),
    pytest.param("https://relay.test/private-endpoint/\x00v1", id="embedded-nul"),
    pytest.param("https://relay.test/private-endpoint/\rv1", id="embedded-cr"),
    pytest.param("https://relay.test/private-endpoint/\x7fv1", id="embedded-del"),
    pytest.param("\thttps://relay.test/private-endpoint/v1", id="leading-tab"),
    pytest.param("https://relay.test/private-endpoint/v1\n", id="trailing-newline"),
])
def test_base_url_control_characters_raise_safe_configuration_error(base_url):
    with pytest.raises(ConfigurationError) as exc_info:
        load_model_config({
            "base_url": base_url,
            "api_key": "sensitive-api-key",
            "model": "m",
        })
    assert exc_info.value.code == "invalid_model_config"
    assert "private-endpoint" not in str(exc_info.value)
    assert "sensitive-api-key" not in str(exc_info.value)


def test_explicit_empty_does_not_fall_back(monkeypatch):
    monkeypatch.setenv("COPY_AGENT_API_KEY", "env-secret")
    with pytest.raises(ConfigurationError):
        load_model_config({"base_url": "https://x.test/v1", "api_key": "", "model": "m"})


def test_model_config_defaults():
    config = ModelConfig(base_url="http://localhost:8000/v1", api_key="test", model="custom")
    assert config.provider == "openai_chat"
    assert config.supports_images is False
    assert config.timeout_seconds == 60
    assert config.temperature is None
    assert config.max_tokens is None

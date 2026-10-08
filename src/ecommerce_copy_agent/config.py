"""Configuration for the built-in OpenAI Chat Completions adapter."""

import os
from typing import Mapping
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from .errors import ConfigurationError


class ModelConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    provider: str = "openai_chat"
    base_url: str
    api_key: SecretStr
    model: str
    supports_images: bool = Field(default=False, strict=True)
    timeout_seconds: float = Field(default=60, gt=0)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)

    @field_validator("provider")
    @classmethod
    def supported_provider(cls, value: str) -> str:
        if value != "openai_chat":
            raise ValueError("Unsupported provider for this configuration loader")
        return value

    @field_validator("base_url")
    @classmethod
    def valid_base_url(cls, value: str) -> str:
        if any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("API base URL contains control characters")
        parsed = urlsplit(value)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("API base URL has an invalid port") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or port == 0
            or "@" in parsed.netloc
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("API base URL must be HTTP(S) with no embedded credentials")
        return value

    @field_validator("api_key")
    @classmethod
    def nonempty_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("API key is required")
        return value

    @field_validator("model")
    @classmethod
    def nonempty_model(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Model name is required")
        return value


_ENV_FIELDS = {
    "base_url": "COPY_AGENT_BASE_URL",
    "api_key": "COPY_AGENT_API_KEY",
    "model": "COPY_AGENT_MODEL",
    "supports_images": "COPY_AGENT_SUPPORTS_IMAGES",
    "timeout_seconds": "COPY_AGENT_TIMEOUT_SECONDS",
}


def load_model_config(values: Mapping[str, object] | None = None) -> ModelConfig:
    """Apply explicit values before supported process environment settings."""
    merged: dict[str, object] = {}
    for field, env_name in _ENV_FIELDS.items():
        if env_name in os.environ:
            raw = os.environ[env_name]
            if field == "supports_images":
                normalized = raw.strip().lower()
                if normalized not in {"true", "false"}:
                    # An explicit value may override a malformed environment value.
                    merged[field] = raw
                else:
                    merged[field] = normalized == "true"
            else:
                merged[field] = raw
    if values is not None:
        merged.update(values)
    try:
        return ModelConfig.model_validate(merged)
    except ValidationError:
        raise ConfigurationError("invalid_model_config", "Model configuration is invalid") from None

"""OpenAI-compatible Chat Completions transport adapter."""

import base64
from contextlib import AsyncExitStack
from typing import Callable

import httpx
import openai

from ..config import ModelConfig
from ..errors import ConfigurationError, ModelServiceError
from ..schemas import TokenUsage
from .base import ModelRequest, ModelResponse


class OpenAIChatAdapter:
    def __init__(
        self,
        config: ModelConfig,
        *,
        transport_factory: Callable[[], httpx.AsyncBaseTransport] | None = None,
    ) -> None:
        self.config = config
        self.model_name = config.model
        self.supports_images = config.supports_images
        self._transport_factory = transport_factory

    async def generate(self, request: ModelRequest) -> ModelResponse:
        if request.images and not self.supports_images:
            raise ConfigurationError("images_unsupported", "The configured model does not support images")

        user_content: str | list[dict[str, object]] = request.user_prompt
        if request.images:
            user_content = [{"type": "text", "text": request.user_prompt}]
            for image in request.images:
                encoded = base64.b64encode(image.data).decode("ascii")
                user_content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:{image.media_type};base64,{encoded}"},
                })

        params: dict[str, object] = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": user_content},
            ],
        }
        if self.config.temperature is not None:
            params["temperature"] = self.config.temperature
        if self.config.max_tokens is not None:
            params["max_tokens"] = self.config.max_tokens

        try:
            async with AsyncExitStack() as stack:
                options: dict[str, object] = {
                    "base_url": self.config.base_url,
                    "api_key": self.config.api_key.get_secret_value(),
                    "timeout": self.config.timeout_seconds,
                    "max_retries": 0,
                }
                if self._transport_factory is None:
                    client = await stack.enter_async_context(openai.AsyncOpenAI(**options))
                else:
                    http_client = await stack.enter_async_context(
                        httpx.AsyncClient(transport=self._transport_factory(), timeout=self.config.timeout_seconds)
                    )
                    client = openai.AsyncOpenAI(**options, http_client=http_client)
                raw_response = await client.chat.completions.with_raw_response.create(**params)
                payload = raw_response.http_response.json()
        except openai.APITimeoutError:
            raise ModelServiceError("model_timeout", "The model request timed out") from None
        except openai.AuthenticationError:
            raise ModelServiceError("model_authentication", "Model authentication failed") from None
        except openai.RateLimitError:
            raise ModelServiceError("model_rate_limited", "The model service rate limit was reached") from None
        except openai.APIStatusError:
            raise ModelServiceError("model_service", "The model service rejected the request") from None
        except openai.APIConnectionError:
            raise ModelServiceError("model_connection", "Cannot connect to the model service") from None
        except openai.APIError:
            raise ModelServiceError("model_service", "The model service request failed") from None
        except ValueError:
            raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None

        if not isinstance(payload, dict):
            raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None
        choices = payload.get("choices")
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None
        message = choices[0].get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None

        usage = None
        raw_usage = payload.get("usage")
        if raw_usage is not None:
            if not isinstance(raw_usage, dict):
                raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None
            counts = tuple(raw_usage.get(field) for field in ("prompt_tokens", "completion_tokens", "total_tokens"))
            if any(value is not None and (type(value) is not int or value < 0) for value in counts):
                raise ModelServiceError("model_response_invalid", "The model service returned an invalid response") from None
            if all(value is not None for value in counts):
                usage = TokenUsage(input_tokens=counts[0], output_tokens=counts[1], total_tokens=counts[2])
        return ModelResponse(text=content, model=self.model_name, usage=usage)

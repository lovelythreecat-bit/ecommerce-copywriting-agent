import base64
import json
import traceback

import httpx
import pytest

from ecommerce_copy_agent.adapters.base import ModelRequest
from ecommerce_copy_agent.adapters.openai_chat import OpenAIChatAdapter
from ecommerce_copy_agent.config import ModelConfig
from ecommerce_copy_agent.errors import ConfigurationError, ModelServiceError
from ecommerce_copy_agent.images import PreparedImage


def config(**overrides):
    values = {"base_url": "https://relay.test/v1", "api_key": "test-secret", "model": "chosen-model"}
    values.update(overrides)
    return ModelConfig(**values)


def response(usage=True):
    body = {"id": "chatcmpl-test", "object": "chat.completion", "created": 1,
            "model": "relay-model", "choices": [{"index": 0, "finish_reason": "stop",
            "message": {"role": "assistant", "content": '{"text":"copy","warnings":[]}'}}]}
    if usage:
        body["usage"] = {"prompt_tokens": 7, "completion_tokens": 5, "total_tokens": 12}
    return httpx.Response(200, json=body)


@pytest.mark.asyncio
async def test_multimodal_payload_and_custom_endpoint():
    seen = []
    def handle(request):
        seen.append(request)
        return response()
    adapter = OpenAIChatAdapter(config(supports_images=True), transport_factory=lambda: httpx.MockTransport(handle))
    result = await adapter.generate(ModelRequest("system", "describe", [PreparedImage(b"abc", "image/png")]))
    payload = json.loads(seen[0].content)
    assert seen[0].url == httpx.URL("https://relay.test/v1/chat/completions")
    assert payload["model"] == "chosen-model"
    assert payload["messages"][0] == {"role": "system", "content": "system"}
    assert payload["messages"][1]["content"] == [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(b"abc").decode()}},
    ]
    assert result.text == '{"text":"copy","warnings":[]}'
    assert result.model == "chosen-model"
    assert result.usage.input_tokens == 7
    assert result.usage.output_tokens == 5
    assert result.usage.total_tokens == 12
    assert "ChatCompletion" not in repr(result)


@pytest.mark.asyncio
async def test_optional_parameters_omitted():
    payloads = []
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(
        lambda request: (payloads.append(json.loads(request.content)), response())[1]))
    await adapter.generate(ModelRequest("s", "u"))
    assert payloads[0]["messages"][1] == {"role": "user", "content": "u"}
    assert not {"temperature", "max_tokens", "tools", "response_format"} & payloads[0].keys()


@pytest.mark.asyncio
async def test_configured_generation_parameters_forwarded():
    payloads = []
    adapter = OpenAIChatAdapter(config(temperature=0.3, max_tokens=80), transport_factory=lambda: httpx.MockTransport(
        lambda request: (payloads.append(json.loads(request.content)), response())[1]))
    await adapter.generate(ModelRequest("s", "u"))
    assert payloads[0]["temperature"] == 0.3
    assert payloads[0]["max_tokens"] == 80


@pytest.mark.asyncio
async def test_image_capability_required():
    calls = []
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: (calls.append(1), httpx.MockTransport(lambda r: response()))[1])
    with pytest.raises(ConfigurationError):
        await adapter.generate(ModelRequest("s", "u", [PreparedImage(b"x", "image/png")]))
    assert calls == []


@pytest.mark.asyncio
async def test_api_error_does_not_leak_secret():
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(
        lambda request: httpx.Response(401, json={"error": {"message": "test-secret echoed"}})))
    with pytest.raises(ModelServiceError) as caught:
        await adapter.generate(ModelRequest("s", "u"))
    assert "test-secret" not in str(caught.value)
    assert "test-secret" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.parametrize("status", [401, 429, 500, "timeout"])
@pytest.mark.asyncio
async def test_no_transport_retries(status):
    calls = []
    def handle(request):
        calls.append(request)
        if status == "timeout":
            raise httpx.ReadTimeout("simulated timeout")
        return httpx.Response(status, json={"error": {"message": "failed"}})
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(handle))
    with pytest.raises(ModelServiceError):
        await adapter.generate(ModelRequest("s", "u"))
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_optional_usage():
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(lambda request: response(False)))
    result = await adapter.generate(ModelRequest("s", "u"))
    assert result.usage is None


@pytest.mark.asyncio
async def test_transport_created_and_closed_per_call():
    class TrackedTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.closes = 0
        async def handle_async_request(self, request):
            if self.closes:
                raise AssertionError("closed transport reused")
            return response()
        async def aclose(self):
            self.closes += 1
    transports = []
    def factory():
        transport = TrackedTransport()
        transports.append(transport)
        return transport
    adapter = OpenAIChatAdapter(config(), transport_factory=factory)
    await adapter.generate(ModelRequest("s", "first"))
    await adapter.generate(ModelRequest("s", "second"))
    assert len(transports) == 2
    assert transports[0] is not transports[1]
    assert [transport.closes for transport in transports] == [1, 1]
    with pytest.raises(AssertionError, match="closed transport reused"):
        await transports[0].handle_async_request(httpx.Request("POST", "https://relay.test/v1/chat/completions"))


@pytest.mark.parametrize("body", [
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": []},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": None}}]},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": None}]},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0}]},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}], "usage": "secret-sentinel"},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}], "usage": {"prompt_tokens": -1, "completion_tokens": 2, "total_tokens": 1}},
    {"id": "x", "object": "chat.completion", "created": 1, "model": "m", "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}], "usage": {"prompt_tokens": True, "completion_tokens": 2, "total_tokens": 3}},
])
@pytest.mark.asyncio
async def test_invalid_response_is_safe_service_error(body):
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    with pytest.raises(ModelServiceError) as caught:
        await adapter.generate(ModelRequest("s", "u"))
    assert caught.value.code == "model_response_invalid"
    assert "secret-sentinel" not in str(caught.value)
    assert "secret-sentinel" not in "".join(traceback.format_exception(caught.value))


@pytest.mark.asyncio
async def test_partial_usage_is_absent():
    body = response().json()
    body["usage"] = {"prompt_tokens": 7, "completion_tokens": 5}
    adapter = OpenAIChatAdapter(config(), transport_factory=lambda: httpx.MockTransport(lambda request: httpx.Response(200, json=body)))
    result = await adapter.generate(ModelRequest("s", "u"))
    assert result.usage is None

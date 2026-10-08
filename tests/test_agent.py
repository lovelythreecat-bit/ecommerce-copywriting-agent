import json
import subprocess
import sys

import httpx
import pytest

from ecommerce_copy_agent.adapters.base import ModelResponse
from ecommerce_copy_agent.adapters.openai_chat import OpenAIChatAdapter
from ecommerce_copy_agent.agent import CopywritingAgent
from ecommerce_copy_agent.config import ModelConfig
from ecommerce_copy_agent.errors import AgentError
from ecommerce_copy_agent.schemas import CopyRequest, ProductInfo


class RepeatAdapter:
    model_name = "repeat-model"
    supports_images = False

    async def generate(self, request):
        return ModelResponse(text=_stage_reply(request.system_prompt), model="returned-model")


def _stage_reply(system_prompt):
    if "STAGE: strategy" in system_prompt:
        value = {
            "facts": ["杯子"], "audience_hypothesis": "日常饮水用户",
            "purchase_motivation": "饮水", "key_message": "日常用杯",
            "benefits": [], "scenarios": [], "objections": [], "call_to_action": "",
            "assumptions": [], "missing_information": [], "source_ids": [],
        }
    elif "STAGE: review" in system_prompt:
        value = {"strengths": [], "issues": [], "factual_risks": []}
    else:
        value = {"text": "好", "warnings": []}
    return json.dumps(value, ensure_ascii=False)


def test_repeated_sync_calls():
    agent = CopywritingAgent(RepeatAdapter())
    request = CopyRequest(product=ProductInfo(name="杯子"))
    assert agent.generate(request).request_count == 4
    assert agent.generate(request).model == "repeat-model"


def test_real_adapter_repeated_sync_calls():
    transports = []
    calls = []

    class TrackingTransport(httpx.MockTransport):
        def __init__(self):
            super().__init__(self.handle)
            self.closed = False

        def handle(self, request):
            calls.append(request)
            payload = json.loads(request.content)
            system_prompt = payload["messages"][0]["content"]
            return httpx.Response(200, json={
                "id": "chatcmpl-test", "object": "chat.completion", "created": 1,
                "model": "relay-model", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": _stage_reply(system_prompt)}}],
            })

        async def aclose(self):
            self.closed = True
            await super().aclose()

    def transport_factory():
        transport = TrackingTransport()
        transports.append(transport)
        return transport

    adapter = OpenAIChatAdapter(
        ModelConfig(base_url="https://relay.test/v1", api_key="test-secret", model="chosen-model"),
        transport_factory=transport_factory,
    )
    agent = CopywritingAgent(adapter)
    request = CopyRequest(product=ProductInfo(name="杯子"))
    assert agent.generate(request).text == "好"
    assert agent.generate(request).text == "好"
    assert len(calls) == 8
    assert len(transports) == 8
    assert all(transport.closed for transport in transports)


@pytest.mark.asyncio
async def test_sync_rejected_inside_event_loop():
    agent = CopywritingAgent(RepeatAdapter())
    with pytest.raises(AgentError, match="agenerate"):
        agent.generate(CopyRequest(product=ProductInfo(name="杯子")))


def test_no_gui_import_in_core():
    process = subprocess.run(
        [sys.executable, "-c", "import ecommerce_copy_agent; import sys; assert 'tkinter' not in sys.modules"],
        capture_output=True, text=True,
    )
    assert process.returncode == 0, process.stderr

"""只走公开导出的最小集成测试，不连接模型服务。"""

from __future__ import annotations

import io
import json
import base64

from PIL import Image

from ecommerce_copy_agent import (
    BytesImage,
    CopyRequest,
    CopywritingAgent,
    ModelResponse,
    ProductInfo,
)


class FakeAdapter:
    model_name = "fake-model"
    supports_images = True

    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, request) -> ModelResponse:
        self.calls += 1
        assert len(request.images) == 1
        if 'STAGE: strategy' in request.system_prompt:
            value = {
                'facts': ['名称是收纳盒'], 'audience_hypothesis': '需要整理物品的人',
                'purchase_motivation': '整理空间', 'key_message': '按用途整理',
                'benefits': [], 'scenarios': ['桌面整理'], 'objections': [],
                'call_to_action': '', 'assumptions': ['受众由场景推测'],
                'missing_information': ['缺少尺寸'], 'source_ids': [],
            }
        elif 'STAGE: review' in request.system_prompt:
            value = {'strengths': [], 'issues': [], 'factual_risks': []}
        else:
            value = {'text': '收纳盒，让物品各有位置。具体尺寸请核实。', 'warnings': []}
        return ModelResponse(
            text=json.dumps(value),
            model=self.model_name,
            usage=None,
        )


def test_public_api_smoke() -> None:
    picture = io.BytesIO()
    Image.new("RGB", (1, 1), "blue").save(picture, format="PNG")
    image_bytes = picture.getvalue()
    adapter = FakeAdapter()
    adapter.api_key = "top-secret-smoke-key"

    result = CopywritingAgent(adapter).generate(
        CopyRequest(
            product=ProductInfo(name="收纳盒"),
            images=[BytesImage(data=image_bytes, media_type="image/png")],
        )
    )

    dumped = result.model_dump_json()
    parsed = json.loads(dumped)
    assert set(parsed) == {"text", "warnings", "model", "usage", "request_count", "strategy", "draft", "review", "sources"}
    assert parsed["request_count"] == adapter.calls == 4
    assert parsed['strategy']['key_message'] == '按用途整理'
    assert parsed['draft'] and parsed['review'] is not None and parsed['sources']
    assert parsed["model"] == "fake-model"
    assert parsed["usage"] is None
    assert "top-secret-smoke-key" not in dumped
    assert image_bytes.hex() not in dumped
    assert base64.b64encode(image_bytes).decode("ascii") not in dumped

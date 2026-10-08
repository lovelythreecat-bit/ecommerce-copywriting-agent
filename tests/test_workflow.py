import asyncio
import json
from io import BytesIO

import pytest
from PIL import Image

from ecommerce_copy_agent import CopywritingAgent
from ecommerce_copy_agent.adapters.base import ModelResponse
from ecommerce_copy_agent.errors import ConfigurationError, ModelServiceError, OutputValidationError
from ecommerce_copy_agent.marketing import KnowledgeSource, WorkflowOptions
from ecommerce_copy_agent.schemas import BytesImage, CopyRequest, CopyRequirements, ProductInfo, TokenUsage


def request(name="茶杯", *, images=None, max_chars=None):
    return CopyRequest(product=ProductInfo(name=name, description="陶瓷杯身", attributes={"容量": "300ml"}),
                       images=images or [], requirements=CopyRequirements(platform="小红书", max_chars=max_chars))


def source(id="S1"):
    return KnowledgeSource(id=id, title="指南", url="https://example.com/guide", summary="属性转具体场景利益。")


class Retriever:
    def __init__(self, sources=None):
        self.sources = [source()] if sources is None else sources

    async def retrieve(self, request):
        return self.sources


def strategy(source_ids=None):
    return {"facts": ["陶瓷杯身"], "audience_hypothesis": "办公室用户",
            "purchase_motivation": "日常饮水", "key_message": "适合日常使用",
            "benefits": ["容量适中"], "scenarios": ["办公桌饮水"], "objections": [],
            "call_to_action": "", "assumptions": ["受众待核实"], "missing_information": ["耐热范围"],
            "source_ids": ["S1"] if source_ids is None else source_ids}


def response(value, usage=None):
    return ModelResponse(text=json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value,
                         model="remote", usage=usage)


class StagedAdapter:
    model_name = "configured"
    supports_images = True

    def __init__(self, stage_values=None):
        self.stage_values = stage_values or {}
        self.requests = []

    async def generate(self, model_request):
        self.requests.append(model_request)
        stage = next(s for s in ("strategy", "draft", "review", "revision")
                     if f"STAGE: {s}" in model_request.system_prompt)
        values = self.stage_values.get(stage)
        value = values.pop(0) if values else {
            "strategy": strategy(), "draft": {"text": "初稿", "warnings": ["草稿提示"]},
            "review": {"strengths": ["具体"], "issues": [{"quote": "初稿", "problem": "场景不足", "suggestion": "写办公桌"}],
                       "factual_risks": ["耐热范围待核实"]},
            "revision": {"text": "办公桌上的300ml陶瓷杯", "warnings": ["定稿提示"]},
        }[stage]
        if isinstance(value, Exception):
            raise value
        return response(value, TokenUsage(input_tokens=1, output_tokens=2, total_tokens=3))


@pytest.mark.asyncio
async def test_four_stages_pass_artifacts_usage_and_warnings():
    adapter = StagedAdapter()
    result = await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request())
    assert (result.text, result.draft, result.request_count, result.usage.total_tokens) == (
        "办公桌上的300ml陶瓷杯", "初稿", 4, 12)
    assert result.strategy.source_ids == ["S1"]
    assert result.review.issues[0].quote == "初稿"
    assert result.sources[0].id == "S1"
    assert any("初稿审稿风险" in item and "耐热范围待核实" in item for item in result.warnings)
    assert "初稿" in adapter.requests[2].user_prompt
    assert "场景不足" in adapter.requests[3].user_prompt
    assert "https://example.com/guide" in adapter.requests[0].user_prompt


@pytest.mark.asyncio
async def test_source_id_repair_and_budget_reserve():
    adapter = StagedAdapter({"strategy": [strategy(["invented"]), strategy(["S1"])]})
    result = await CopywritingAgent(adapter, retriever=Retriever(),
                                    workflow_options=WorkflowOptions(max_model_calls=5)).agenerate(request())
    assert result.request_count == 5
    assert "invented" in adapter.requests[1].user_prompt
    adapter = StagedAdapter({"strategy": [strategy(["invented"])]})
    with pytest.raises(OutputValidationError):
        await CopywritingAgent(adapter, retriever=Retriever(),
                               workflow_options=WorkflowOptions(max_model_calls=4)).agenerate(request())
    assert len(adapter.requests) == 1


@pytest.mark.asyncio
async def test_bounded_sources_empty_warning_and_safe_errors():
    adapter = StagedAdapter()
    result = await CopywritingAgent(adapter, retriever=Retriever([source(), source(), source("S2")]),
                                    workflow_options=WorkflowOptions(max_sources=1)).agenerate(request())
    assert [item.id for item in result.sources] == ["S1"]
    result = await CopywritingAgent(StagedAdapter({"strategy": [strategy([])]}),
                                    retriever=Retriever([])).agenerate(request())
    assert any("资料" in warning for warning in result.warnings)
    with pytest.raises(ModelServiceError) as error:
        await CopywritingAgent(StagedAdapter({"strategy": [RuntimeError("secret-token")]}),
                               retriever=Retriever()).agenerate(request())
    assert "secret-token" not in str(error.value)


@pytest.mark.asyncio
async def test_timeout_covers_retrieval():
    class SlowRetriever:
        async def retrieve(self, request):
            await asyncio.sleep(0.1)
            return []

    with pytest.raises(ModelServiceError) as error:
        await CopywritingAgent(StagedAdapter(), retriever=SlowRetriever(),
                               workflow_options=WorkflowOptions(timeout_seconds=0.01)).agenerate(request())
    assert error.value.code == "workflow_timeout"


@pytest.mark.asyncio
async def test_images_preserved_each_stage_and_capability_checked():
    stream = BytesIO()
    Image.new("RGB", (2, 2), "red").save(stream, format="PNG")
    data = stream.getvalue()
    adapter = StagedAdapter()
    image_request = request(images=[BytesImage(data=data, media_type="image/png")])
    await CopywritingAgent(adapter, retriever=Retriever()).agenerate(image_request)
    assert all(call.images[0].data == data for call in adapter.requests)
    adapter.supports_images = False
    adapter.requests.clear()
    with pytest.raises(ConfigurationError):
        await CopywritingAgent(adapter, retriever=Retriever()).agenerate(image_request)
    assert adapter.requests == []


@pytest.mark.asyncio
async def test_concurrent_calls_are_isolated():
    class EchoAdapter(StagedAdapter):
        async def generate(self, model_request):
            await asyncio.sleep(0)
            name = "甲" if "甲" in model_request.user_prompt else "乙"
            stage = next(s for s in ("strategy", "draft", "review", "revision")
                         if f"STAGE: {s}" in model_request.system_prompt)
            if stage == "strategy":
                value = strategy([]) | {"key_message": name}
            elif stage == "review":
                value = {"strengths": [], "issues": [], "factual_risks": []}
            else:
                value = {"text": name, "warnings": []}
            return response(value)

    agent = CopywritingAgent(EchoAdapter(), retriever=Retriever([]))
    a, b = await asyncio.gather(agent.agenerate(request("甲")), agent.agenerate(request("乙")))
    assert (a.text, a.strategy.key_message, b.text, b.strategy.key_message) == ("甲", "甲", "乙", "乙")


@pytest.mark.asyncio
async def test_two_repairs_are_shared_across_stages_and_exhausted():
    adapter = StagedAdapter({"strategy": ["bad", "still bad", "also bad"]})
    with pytest.raises(OutputValidationError):
        await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request())
    assert len(adapter.requests) == 3
    assert all("STAGE: strategy" in item.system_prompt for item in adapter.requests)


@pytest.mark.asyncio
async def test_final_length_repair_preserves_review_and_missing_usage():
    adapter = StagedAdapter({"revision": [
        {"text": "这是一段超过上限的文案", "warnings": []},
        {"text": "短文案", "warnings": []},
    ]})
    result = await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request(max_chars=4))
    assert result.text == "短文案"
    assert result.request_count == 5
    assert "场景不足" in adapter.requests[-1].user_prompt
    assert "正文超过最大字符数" in adapter.requests[-1].user_prompt

    class MissingUsageAdapter(StagedAdapter):
        async def generate(self, model_request):
            value = await super().generate(model_request)
            if "STAGE: review" in model_request.system_prompt:
                return ModelResponse(text=value.text, model=value.model, usage=None)
            return value

    result = await CopywritingAgent(MissingUsageAdapter(), retriever=Retriever()).agenerate(request())
    assert result.usage is None


@pytest.mark.asyncio
async def test_review_quote_and_noop_revision_are_repaired():
    adapter = StagedAdapter({"review": [
        {"strengths": [], "issues": [{"quote": "未出现原句", "problem": "空泛", "suggestion": "补场景"}], "factual_risks": []},
        {"strengths": [], "issues": [{"quote": "初稿", "problem": "空泛", "suggestion": "补场景"}], "factual_risks": []},
    ], "revision": [{"text": "初稿", "warnings": []}, {"text": "办公桌上的杯子", "warnings": []}]})
    result = await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request())
    assert result.request_count == 6
    assert result.text == "办公桌上的杯子"
    adapter = StagedAdapter({"revision": [{"text": "初稿", "warnings": []},
                                           {"text": "办公桌上的杯子", "warnings": []}]})
    result = await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request())
    assert result.text == "办公桌上的杯子"
    assert result.request_count == 5


@pytest.mark.asyncio
async def test_service_failure_does_not_trigger_repair():
    adapter = StagedAdapter({"review": [ModelServiceError("rate_limited", "Rate limited")]})
    with pytest.raises(ModelServiceError) as error:
        await CopywritingAgent(adapter, retriever=Retriever()).agenerate(request())
    assert error.value.code == "rate_limited"
    assert len(adapter.requests) == 3


@pytest.mark.asyncio
async def test_retrieved_source_is_revalidated_and_result_independent():
    original = source()
    original.tags.append("通用")
    adapter = StagedAdapter()
    result = await CopywritingAgent(adapter, retriever=Retriever([original])).agenerate(request())
    result.sources[0].tags.append("mutated")
    assert original.tags == ["通用"]
    unsafe = source().model_copy(update={"url": "https://@example.com"})
    with pytest.raises(ModelServiceError) as error:
        await CopywritingAgent(StagedAdapter(), retriever=Retriever([unsafe])).agenerate(request())
    assert error.value.code == "knowledge_retrieval_failed"

"""Regression for user-reported copy; synthetic replies only test enforcement."""

import importlib
import json

import pytest

from ecommerce_copy_agent import CopyRequest, CopyRequirements, CopywritingAgent, ModelResponse, ProductInfo
from ecommerce_copy_agent.errors import OutputValidationError


REPORTED_COPY = (
    '索尼游戏手柄\n\n这是一款索尼品牌游戏手柄，在淘宝、京东、拼多多游戏工具分类下可按品牌快速筛选。'
    '对偏好索尼品牌的玩家来说，品牌信息明确，便于纳入备选比较。'
    '具体型号、适配平台、连接方式、按键布局、续航与售后政策，请以商品详情页为准；确认适合后再加购。'
)


def request(**requirements):
    # Reconstructed minimal input, not a claim to have recovered the user's original form.
    return CopyRequest(product=ProductInfo(name='索尼游戏手柄', brand='索尼'),
                       requirements=CopyRequirements(**requirements))


def findings(text, req):
    return importlib.import_module('ecommerce_copy_agent.editorial').editorial_findings(text, req)


def test_reported_copy_exposes_metadata_pitch_and_missing_data_in_body():
    issues = findings(REPORTED_COPY, request())
    assert any('卖点' in item.problem for item in issues)
    assert any('提示' in item.suggestion for item in issues)
    assert all(item.quote in REPORTED_COPY for item in issues)


@pytest.mark.parametrize('text', [
    '下一局，轮到你上场。索尼游戏手柄，今晚给自己留一点游戏时间。',
    '索尼游戏手柄，仅适用于 PS5，不支持 PS4。',
    '活动价格以结算页为准。',
])
def test_no_blanket_ban_on_creativity_or_necessary_product_disclosures(text):
    assert findings(text, request()) == []


def test_explicit_disclosure_and_non_ad_copy_remain_supported():
    disclaimer = '具体适配平台请以商品详情页为准。'
    assert findings(disclaimer, request(extra_instructions='请保留：' + disclaimer)) == []
    assert findings(disclaimer, request(copy_type='选购指南')) == []
    req = request()
    req.product.description = '这是商品筛选软件，支持按品牌快速筛选。'
    assert findings('支持按品牌快速筛选。', req) == []


@pytest.mark.parametrize('instruction', [
    '请保留：适配平台以商品详情页为准。',
    '正文必须提醒买家：购买前核对商品详情页中的适配设备列表。',
])
def test_requested_compatibility_disclosure_can_be_paraphrased(instruction):
    assert findings('下一局，轮到你上场。适配平台请以商品详情页为准。',
                    request(extra_instructions=instruction)) == []


def test_prohibited_phrase_is_not_treated_as_requested_disclosure():
    assert findings('适配平台请以商品详情页为准。',
                    request(extra_instructions='不要写“请以商品详情页为准”。'))


class CopyFixture:
    model_name = 'fixture-not-quality-evaluation'
    supports_images = False

    def __init__(self, repeated_bad=False):
        self.requests = []
        self.revisions = 0
        self.repeated_bad = repeated_bad

    async def generate(self, req):
        self.requests.append(req)
        if 'STAGE: strategy' in req.system_prompt:
            value = dict(facts=['索尼游戏手柄'], audience_hypothesis='想玩游戏的人',
                         purchase_motivation='享受游戏时间', key_message='给自己留一点游戏时间',
                         benefits=[], scenarios=['休息时玩游戏'], objections=[], call_to_action='',
                         assumptions=['使用场景是创作角度'], missing_information=['未提供型号与兼容信息'], source_ids=[])
        elif 'STAGE: review' in req.system_prompt:
            value = dict(strengths=[], issues=[], factual_risks=[])
        elif 'STAGE: draft' in req.system_prompt:
            value = dict(text=REPORTED_COPY, warnings=[])
        else:
            self.revisions += 1
            value = dict(text=REPORTED_COPY + '欢迎选购。' if self.repeated_bad or self.revisions == 1
                         else '下一局，轮到你上场。索尼游戏手柄，今晚给自己留一点游戏时间。',
                         warnings=['型号与兼容信息未提供'])
        return ModelResponse(text=json.dumps(value, ensure_ascii=False), model=self.model_name)


@pytest.mark.asyncio
async def test_empty_model_review_cannot_let_reported_failure_pass():
    model = CopyFixture()
    result = await CopywritingAgent(model).agenerate(request())
    assert result.request_count == 5
    assert result.review.issues  # deterministic findings remain even if model missed them
    assert 'editorial_findings' in model.requests[2].user_prompt
    assert any('提示' in item.suggestion for item in result.review.issues)
    assert '请以商品详情页为准' not in result.text
    assert result.warnings


@pytest.mark.asyncio
async def test_persistent_failure_exhausts_existing_budget_without_canned_fallback():
    model = CopyFixture(repeated_bad=True)
    with pytest.raises(OutputValidationError):
        await CopywritingAgent(model).agenerate(request())
    assert len(model.requests) == 6

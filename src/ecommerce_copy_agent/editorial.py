"""Narrow, explainable checks for leaked authoring notes, not a quality score."""

import json
import re

from .marketing import ReviewIssue
from .schemas import CopyRequest


_AD_TYPES = re.compile(r'宣传|广告|推广|种草|营销|详情|卖点|标题|社交|口播|海报')
_GUIDE_TYPES = re.compile(r'指南|选购建议|客服|售后|免责声明|风险提示|合规提示|参数核对|常见问题|兼容性说明|faq', re.I)
_METADATA = re.compile(r'品牌信息(?:明确|清晰)|(?:便于|方便|可以|可)纳入(?:备选|候选)(?:比较|对比)?|按品牌(?:快速|进行)?筛选')
_MISSING_DATA = re.compile(r'(?:请)?以(?:商品详情页|商品详情|详情页|商品页面)为准')
_NEGATED = re.compile(r'不要(?:写|加|放|包含|使用|标注|出现)|不得|禁止|避免|别(?:写|加|放)|不应|无需')
_DISCLOSURE_REQUEST = re.compile(r'保留|注明|标注|提醒|说明|披露|写明|包含|核对|提示')
_DISCLOSURE_TOPIC = re.compile(r'详情|兼容|适配|售后|参数|限制|安全')


def _requested(quote: str, instructions: str, *, disclosure: bool) -> bool:
    # Accept paraphrased, explicitly requested disclosures without treating a
    # quoted "do not write this" as permission to repeat it.
    canonical = quote.removeprefix('请')
    for clause in re.split(r'[，,。！？!?;；\n]', instructions):
        if _NEGATED.search(clause):
            continue
        if canonical in clause:
            return True
        if disclosure and _DISCLOSURE_REQUEST.search(clause) and _DISCLOSURE_TOPIC.search(clause):
            return True
    return False


def editorial_findings(text: str, request: CopyRequest) -> list[ReviewIssue]:
    """Flag two known failure families only in promotional copy.

    Explicitly supplied disclosures/features are retained. Unknown/custom copy
    types rely on model editing; these heuristics are not semantic fact checks.
    """
    copy_type = request.requirements.copy_type
    if not _AD_TYPES.search(copy_type) or _GUIDE_TYPES.search(copy_type):
        return []
    supplied = json.dumps(request.product.model_dump(mode='json'), ensure_ascii=False)
    explicit = request.requirements.extra_instructions
    findings = []
    for pattern, problem, suggestion in (
        (_METADATA, '把商品分类或内部选品分析当成消费者卖点。',
         '删除内部筛选和比较措辞，用真实属性的价值或具体使用场景表达；资料少时写短广告，不编造性能。'),
        (_MISSING_DATA, '用泛化的详情页核对说明代替了宣传正文。',
         '把缺失参数与待核实事项放进 warnings 提示区，正文围绕已知商品与使用愿望写作；保留用户提供或明确要求的必要限制。'),
    ):
        for match in pattern.finditer(text):
            quote = match.group()
            if quote.removeprefix('请') not in supplied and not _requested(quote, explicit, disclosure=pattern is _MISSING_DATA):
                findings.append(ReviewIssue(quote=quote, problem=problem, suggestion=suggestion))
    return findings

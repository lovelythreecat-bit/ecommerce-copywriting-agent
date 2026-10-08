"""Local validation of the model's JSON response."""

from dataclasses import dataclass
import json
import re
from pydantic import ValidationError

from .marketing import EditorialReview, MarketingStrategy

from .errors import OutputValidationError
from .schemas import CopyRequirements


_FENCE = re.compile(r"\A```(?:json)?[ \t]*\r?\n(.*?)\r?\n```\Z", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True, slots=True)
class ValidatedCopy:
    text: str
    warnings: list[str]


def _invalid(problem: str) -> OutputValidationError:
    return OutputValidationError("invalid_model_output", "Model output did not satisfy the copy result contract", problems=[problem])


def validate_output(raw: str, requirements: CopyRequirements) -> ValidatedCopy:
    """Accept one JSON object, optionally enclosed in a complete JSON fence."""
    if not isinstance(raw, str):
        raise _invalid("模型输出必须是 JSON 文本")
    candidate = raw.strip()
    fenced = _FENCE.fullmatch(candidate)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        raise _invalid("模型输出必须是一个完整的 JSON 对象") from None
    if not isinstance(value, dict):
        raise _invalid("模型输出必须是 JSON 对象")
    if not isinstance(value.get("text"), str) or not value["text"].strip():
        raise _invalid("正文 text 必须是非空字符串")
    warnings = value.get("warnings")
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        raise _invalid("warnings 必须是字符串数组")
    text = value["text"].strip()
    if requirements.max_chars is not None and len(text) > requirements.max_chars:
        raise _invalid("正文超过最大字符数")
    return ValidatedCopy(text=text, warnings=warnings)


def validate_artifact(raw: str, artifact_type: type[MarketingStrategy] | type[EditorialReview]):
    """Decode a strict stage artifact without exposing model content in errors."""
    if not isinstance(raw, str):
        raise _invalid("阶段输出必须是 JSON 文本")
    candidate = raw.strip()
    fenced = _FENCE.fullmatch(candidate)
    if fenced:
        candidate = fenced.group(1)
    try:
        value = json.loads(candidate)
    except (json.JSONDecodeError, ValueError):
        raise _invalid("阶段输出必须是完整 JSON 对象") from None
    if not isinstance(value, dict):
        raise _invalid("阶段输出必须是 JSON 对象")
    try:
        return artifact_type.model_validate(value)
    except ValidationError:
        raise _invalid("阶段输出字段缺失或类型不正确") from None

"""Convert desktop form values into the public request contract."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping

from ecommerce_copy_agent.schemas import CopyRequest, CopyRequirements, FileImage, ProductInfo


def parse_attributes_json(text: str) -> dict:
    if not text.strip():
        return {}
    try:
        attributes = json.loads(text)
    except (json.JSONDecodeError, ValueError) as error:
        raise ValueError("商品属性必须是有效的 JSON 对象。") from error
    if not isinstance(attributes, dict):
        raise ValueError("商品属性必须是 JSON 对象。")
    for key, value in attributes.items():
        if not isinstance(key, str) or not (
            isinstance(value, (str, bool))
            or (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value))
            or (isinstance(value, list) and all(isinstance(item, str) for item in value))
        ):
            raise ValueError(f"商品属性“{key}”只支持文字、有限数字、布尔值或文字列表。")
    return attributes


def build_request(values: Mapping[str, str], image_paths: list[Path]) -> CopyRequest:
    max_chars_text = values.get("max_chars", "").strip()
    max_chars = None
    if max_chars_text:
        try:
            max_chars = int(max_chars_text)
        except ValueError as error:
            raise ValueError("最大字符数必须是正整数。") from error
        if max_chars <= 0:
            raise ValueError("最大字符数必须是正整数。")

    product = ProductInfo(
        name=values.get("name", "").strip(),
        category=values.get("category", "").strip(),
        brand=values.get("brand", "").strip(),
        description=values.get("description", "").strip(),
        attributes=parse_attributes_json(values.get("attributes_json", "")),
    )
    requirements = CopyRequirements(
        copy_type=values.get("copy_type", "宣传文案").strip() or "宣传文案",
        platform=values.get("platform", "").strip(),
        audience=values.get("audience", "").strip(),
        tone=values.get("tone", "自然").strip() or "自然",
        language="简体中文",
        max_chars=max_chars,
        extra_instructions=values.get("extra_instructions", "").strip(),
    )
    return CopyRequest(
        product=product,
        requirements=requirements,
        images=[FileImage(path=path) for path in image_paths],
    )

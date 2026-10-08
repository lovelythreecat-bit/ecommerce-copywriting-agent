from pathlib import Path

import pytest

from desktop.forms import build_request, parse_attributes_json


@pytest.mark.parametrize("source", ["{oops", '["red", "blue"]', '{"规格": {"容量": "1L"}}'])
def test_invalid_attributes_json(source: str) -> None:
    with pytest.raises(ValueError, match="属性"):
        parse_attributes_json(source)


def test_blank_attributes_are_empty() -> None:
    assert parse_attributes_json("  \n ") == {}


def test_form_maps_custom_requirements() -> None:
    paths = [Path("C:/图片/正面.png"), Path("C:/图片/背面.jpg")]
    request = build_request(
        {
            "name": "保温杯",
            "attributes_json": '{"容量": "500毫升", "保温小时": 8}',
            "description": "轻巧便携",
            "copy_type": "直播口播",
            "platform": "小红书",
            "audience": "通勤族",
            "tone": "活泼",
            "max_chars": "120",
            "extra_instructions": "强调清洗方便",
        },
        paths,
    )
    assert request.product.name == "保温杯"
    assert request.product.attributes == {"容量": "500毫升", "保温小时": 8}
    assert request.product.description == "轻巧便携"
    assert request.requirements.copy_type == "直播口播"
    assert request.requirements.platform == "小红书"
    assert request.requirements.audience == "通勤族"
    assert request.requirements.tone == "活泼"
    assert request.requirements.language == "简体中文"
    assert request.requirements.max_chars == 120
    assert request.requirements.extra_instructions == "强调清洗方便"
    assert [image.path for image in request.images] == paths


@pytest.mark.parametrize("value", ["0", "-3", "1.5", "abc"])
def test_bad_max_chars_is_readable(value: str) -> None:
    with pytest.raises(ValueError, match="最大字符数"):
        build_request({"name": "保温杯", "max_chars": value}, [])

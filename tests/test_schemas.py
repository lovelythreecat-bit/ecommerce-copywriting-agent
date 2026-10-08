import json

import pytest
from pydantic import ValidationError

from ecommerce_copy_agent.schemas import (
    BytesImage,
    CopyRequest,
    CopyRequirements,
    ProductInfo,
)


def test_blank_product_rejected():
    with pytest.raises(ValidationError):
        ProductInfo(name="   ")


def test_requirements_defaults():
    requirements = CopyRequirements()
    assert requirements.language == "简体中文"
    assert requirements.copy_type == "宣传文案"


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_max_chars_is_strict_positive_integer(value):
    with pytest.raises(ValidationError):
        CopyRequirements(max_chars=value)


def test_custom_attributes_and_copy_type():
    product = ProductInfo(name="茶杯", attributes={"容量": 350, "可微波": False, "颜色": ["蓝", "白"]})
    requirements = CopyRequirements(copy_type="直播口播")
    assert product.attributes == {"容量": 350, "可微波": False, "颜色": ["蓝", "白"]}
    assert requirements.copy_type == "直播口播"


@pytest.mark.parametrize("value", [{"nested": {"a": 1}}, {"mixed": ["x", 1]}, {"none": None}, {"inf": float("inf")}])
def test_attributes_reject_invalid_values(value):
    with pytest.raises(ValidationError):
        ProductInfo(name="茶杯", attributes=value)


def test_unknown_fields_rejected():
    with pytest.raises(ValidationError):
        CopyRequirements(platfrom="淘宝")


def test_image_json_roundtrip():
    request = CopyRequest(product=ProductInfo(name="茶杯"), images=[BytesImage(data=b"\x00\xffabc", media_type="image/png")])
    encoded = request.model_dump_json()
    assert "AP9hYmM=" in encoded
    restored = CopyRequest.model_validate_json(encoded)
    assert isinstance(restored.images[0], BytesImage)
    assert restored.images[0].data == b"\x00\xffabc"


def test_image_json_uses_pydantic_url_safe_base64():
    image = BytesImage(data=b"\xfb\xff", media_type="image/png")
    encoded = image.model_dump_json()
    assert json.loads(encoded)["data"] == "-_8="
    assert BytesImage.model_validate_json(encoded).data == b"\xfb\xff"


def test_request_defaults_are_isolated():
    first = CopyRequest(product=ProductInfo(name="茶杯"))
    second = CopyRequest(product=ProductInfo(name="帽子"))
    first.images.append(BytesImage(data=b"x", media_type="image/png"))
    first.product.selling_points.append("耐用")
    assert second.images == []
    assert second.product.selling_points == []


def test_bytes_are_hidden_from_repr():
    image = BytesImage(data=b"private-picture", media_type="image/png")
    assert "private-picture" not in repr(image)

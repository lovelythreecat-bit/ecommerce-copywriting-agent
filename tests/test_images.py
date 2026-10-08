from io import BytesIO

import pytest
from PIL import Image

from ecommerce_copy_agent.errors import InputError
from ecommerce_copy_agent.images import prepare_images
from ecommerce_copy_agent.schemas import BytesImage, FileImage


def png_bytes(size=(2, 2)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, "red").save(stream, format="PNG")
    return stream.getvalue()


def test_chinese_path_image(tmp_path):
    path = tmp_path / "商品图.png"
    content = png_bytes()
    path.write_bytes(content)
    prepared = prepare_images([FileImage(path=path)])
    assert len(prepared) == 1
    assert prepared[0].data == content
    assert prepared[0].media_type == "image/png"


def test_image_limits(tmp_path):
    content = png_bytes()
    with pytest.raises(InputError) as count_error:
        prepare_images([BytesImage(data=content, media_type="image/png")] * 5)
    assert count_error.value.code == "too_many_images"
    oversized = tmp_path / "large.png"
    oversized.write_bytes(b"0" * (10 * 1024 * 1024 + 1))
    with pytest.raises(InputError) as size_error:
        prepare_images([FileImage(path=oversized)])
    assert size_error.value.code == "image_too_large"


@pytest.mark.parametrize("scenario", ["corrupt", "wrong_extension", "wrong_mime", "directory", "unsupported"])
def test_invalid_image_inputs(tmp_path, scenario):
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"not an image")
    wrong_extension = tmp_path / "photo.jpg"
    wrong_extension.write_bytes(png_bytes())
    bmp = tmp_path / "photo.bmp"
    Image.new("RGB", (2, 2)).save(bmp)
    cases = {
        "corrupt": (FileImage(path=corrupt), "image_invalid"),
        "wrong_extension": (FileImage(path=wrong_extension), "image_type_mismatch"),
        "wrong_mime": (BytesImage(data=png_bytes(), media_type="image/jpeg"), "image_type_mismatch"),
        "directory": (FileImage(path=tmp_path), "image_unreadable"),
        "unsupported": (FileImage(path=bmp), "image_unsupported"),
    }
    image, expected_code = cases[scenario]
    with pytest.raises(InputError) as error:
        prepare_images([image])
    assert error.value.code == expected_code


def test_animated_image_rejected():
    stream = BytesIO()
    frames = [Image.new("RGB", (2, 2), color) for color in ("red", "blue")]
    frames[0].save(stream, format="WEBP", save_all=True, append_images=frames[1:], duration=100)
    with pytest.raises(InputError) as error:
        prepare_images([BytesImage(data=stream.getvalue(), media_type="image/webp")])
    assert error.value.code == "image_animated"


def test_decompression_bomb_rejected(monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 10)
    with pytest.raises(InputError) as error:
        prepare_images([BytesImage(data=png_bytes((20, 20)), media_type="image/png")])
    assert error.value.code == "image_invalid"


def test_image_repr_hides_bytes():
    prepared = prepare_images([BytesImage(data=png_bytes(), media_type="image/png")])[0]
    assert "\\x89PNG" not in repr(prepared)

"""Validate and prepare untrusted local image inputs."""

from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
import warnings

from PIL import Image, UnidentifiedImageError

from .errors import InputError
from .schemas import BytesImage, FileImage, ImageInput


MAX_IMAGES = 4
MAX_IMAGE_BYTES = 10 * 1024 * 1024
_FORMAT_TO_MEDIA = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
_EXTENSION_TO_FORMAT = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}


@dataclass(frozen=True, slots=True)
class PreparedImage:
    data: bytes = field(repr=False)
    media_type: str


def _read_file(path: Path) -> bytes:
    try:
        if not path.is_file():
            raise InputError("image_unreadable", "Image file is not readable")
        if path.stat().st_size > MAX_IMAGE_BYTES:
            raise InputError("image_too_large", "Image exceeds the 10 MiB limit")
        with path.open("rb") as source:
            data = source.read(MAX_IMAGE_BYTES + 1)
    except OSError as exc:
        raise InputError("image_unreadable", "Image file is not readable") from exc
    if len(data) > MAX_IMAGE_BYTES:
        raise InputError("image_too_large", "Image exceeds the 10 MiB limit")
    return data


def _actual_format(data: bytes) -> str:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                if image_format not in _FORMAT_TO_MEDIA:
                    raise InputError("image_unsupported", "Image format is not supported")
                if getattr(image, "n_frames", 1) != 1:
                    raise InputError("image_animated", "Animated images are not supported")
                image.verify()
            with Image.open(BytesIO(data)) as image:
                image.load()
        return image_format
    except InputError:
        raise
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
        raise InputError("image_invalid", "Image cannot be decoded safely") from exc


def prepare_images(images: list[ImageInput]) -> list[PreparedImage]:
    """Read, check, and return at most four static JPEG, PNG, or WebP images."""
    if len(images) > MAX_IMAGES:
        raise InputError("too_many_images", "At most four images are allowed")
    prepared = []
    for image in images:
        if isinstance(image, FileImage):
            data = _read_file(image.path)
        elif isinstance(image, BytesImage):
            data = image.data
            if len(data) > MAX_IMAGE_BYTES:
                raise InputError("image_too_large", "Image exceeds the 10 MiB limit")
        else:
            raise InputError("image_invalid", "Unsupported image input")

        actual_format = _actual_format(data)
        media_type = _FORMAT_TO_MEDIA[actual_format]
        if isinstance(image, FileImage):
            suffix = image.path.suffix.lower()
            if suffix and _EXTENSION_TO_FORMAT.get(suffix) != actual_format:
                raise InputError("image_type_mismatch", "Image extension does not match its content")
        elif image.media_type.lower() != media_type:
            raise InputError("image_type_mismatch", "Image media type does not match its content")
        prepared.append(PreparedImage(data=data, media_type=media_type))
    return prepared

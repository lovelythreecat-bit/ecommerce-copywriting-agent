"""Public, provider-independent request and result types."""

from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, field_validator


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


AttributeNumber = Annotated[StrictFloat, Field(allow_inf_nan=False)]
AttributeValue = StrictStr | StrictInt | AttributeNumber | StrictBool | list[StrictStr]


class ProductInfo(PublicModel):
    name: str
    category: str = ""
    brand: str = ""
    description: str = ""
    selling_points: list[str] = Field(default_factory=list)
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Product name cannot be blank")
        return value


class CopyRequirements(PublicModel):
    copy_type: str = "宣传文案"
    platform: str = ""
    audience: str = ""
    tone: str = "自然"
    language: str = "简体中文"
    max_chars: Annotated[int, Field(strict=True, gt=0)] | None = None
    extra_instructions: str = ""


class FileImage(PublicModel):
    kind: Literal["file"] = "file"
    path: Path


class BytesImage(PublicModel):
    model_config = ConfigDict(extra="forbid", strict=True, ser_json_bytes="base64", val_json_bytes="base64")

    kind: Literal["bytes"] = "bytes"
    data: bytes = Field(repr=False)
    media_type: str


ImageInput = Annotated[FileImage | BytesImage, Field(discriminator="kind")]


class CopyRequest(PublicModel):
    product: ProductInfo
    images: list[ImageInput] = Field(default_factory=list)
    requirements: CopyRequirements = Field(default_factory=CopyRequirements)


class TokenUsage(PublicModel):
    input_tokens: Annotated[int, Field(strict=True, ge=0)]
    output_tokens: Annotated[int, Field(strict=True, ge=0)]
    total_tokens: Annotated[int, Field(strict=True, ge=0)]


class CopyResult(PublicModel):
    text: str
    warnings: list[str]
    model: str
    usage: TokenUsage | None
    request_count: Annotated[int, Field(strict=True, ge=1)]
    strategy: "MarketingStrategy | None" = None
    draft: str = ""
    review: "EditorialReview | None" = None
    sources: list["KnowledgeSource"] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def text_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Copy text cannot be blank")
        return value


from .marketing import EditorialReview, KnowledgeSource, MarketingStrategy  # noqa: E402
CopyResult.model_rebuild()

"""Provider-independent model exchange contract."""

from dataclasses import dataclass, field
from typing import Protocol

from ..images import PreparedImage
from ..schemas import TokenUsage


@dataclass(frozen=True, slots=True)
class ModelRequest:
    system_prompt: str
    user_prompt: str
    images: list[PreparedImage] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ModelResponse:
    text: str
    model: str
    usage: TokenUsage | None = None


class ModelAdapter(Protocol):
    model_name: str
    supports_images: bool

    async def generate(self, request: ModelRequest) -> ModelResponse:
        ...

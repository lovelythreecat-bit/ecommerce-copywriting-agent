"""Public typed artifacts and limits for the marketing workflow."""

import math
from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, StrictFloat, StrictInt, StrictStr, field_validator


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class KnowledgeSource(PublicModel):
    id: StrictStr
    title: StrictStr
    url: StrictStr
    summary: StrictStr
    tags: list[StrictStr] = Field(default_factory=list)
    origin: Literal["curated", "web", "custom"] = "curated"
    accessed_on: StrictStr = ""

    @field_validator("id", "title", "url")
    @classmethod
    def required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Source identifier, title and URL are required")
        return value

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        try:
            parts = urlsplit(value)
            hostname = parts.hostname
            port = parts.port
        except ValueError:
            raise ValueError("Source URL is malformed") from None
        if parts.scheme not in ("http", "https") or not hostname or "@" in parts.netloc:
            raise ValueError("Source URL must be HTTP(S) without credentials")
        if port is not None and not 1 <= port <= 65535:
            raise ValueError("Source URL port is invalid")
        if any(ord(character) <= 32 or ord(character) == 127 for character in value):
            raise ValueError("Source URL cannot contain controls or spaces")
        return value


class MarketingStrategy(PublicModel):
    facts: list[StrictStr]
    audience_hypothesis: StrictStr
    purchase_motivation: StrictStr
    key_message: StrictStr
    benefits: list[StrictStr]
    scenarios: list[StrictStr]
    objections: list[StrictStr]
    call_to_action: StrictStr
    assumptions: list[StrictStr]
    missing_information: list[StrictStr]
    source_ids: list[StrictStr]

    @field_validator("audience_hypothesis", "purchase_motivation", "key_message")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Strategy field cannot be blank")
        return value


class ReviewIssue(PublicModel):
    quote: StrictStr
    problem: StrictStr
    suggestion: StrictStr

    @field_validator("quote", "problem", "suggestion")
    @classmethod
    def meaningful_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Review issue field cannot be blank")
        return value


class EditorialReview(PublicModel):
    strengths: list[StrictStr]
    issues: list[ReviewIssue]
    factual_risks: list[StrictStr]


class WorkflowOptions(PublicModel):
    max_model_calls: Annotated[StrictInt, Field(ge=4, le=12)] = 6
    timeout_seconds: StrictFloat | StrictInt = 300
    max_sources: Annotated[StrictInt, Field(ge=1, le=10)] = 5
    max_source_chars: Annotated[StrictInt, Field(ge=1000, le=30000)] = 12000

    @field_validator("timeout_seconds")
    @classmethod
    def positive_finite_timeout(cls, value: float | int) -> float | int:
        if not math.isfinite(value) or value <= 0:
            raise ValueError("Timeout must be positive and finite")
        return value

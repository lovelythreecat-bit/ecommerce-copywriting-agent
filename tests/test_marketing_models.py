import math

import pytest
from pydantic import ValidationError

from ecommerce_copy_agent.marketing import KnowledgeSource, MarketingStrategy, ReviewIssue, EditorialReview, WorkflowOptions


def test_source_url_and_options_are_strict():
    source = KnowledgeSource(id="S1", title="指南", url="https://example.com/x", summary="摘要")
    assert source.origin == "curated"
    for url in ("ftp://example.com", "https://user:pass@example.com", "https:///missing"):
        with pytest.raises(ValidationError):
            KnowledgeSource(id="S1", title="指南", url=url, summary="摘要")
    for values in ({"max_model_calls": True}, {"timeout_seconds": math.inf},
                   {"max_sources": False}, {"max_source_chars": 99}):
        with pytest.raises(ValidationError):
            WorkflowOptions(**values)


def test_artifacts_require_complete_typed_fields():
    with pytest.raises(ValidationError):
        MarketingStrategy(facts=[])
    with pytest.raises(ValidationError):
        ReviewIssue(quote="", problem="bad", suggestion="fix")
    with pytest.raises(ValidationError):
        EditorialReview(strengths=[], issues=[{"quote": "x", "problem": "p", "suggestion": "s", "extra": 1}], factual_risks=[])

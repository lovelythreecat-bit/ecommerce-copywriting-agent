"""Behavioral checks for the independent local knowledge retriever."""

import pytest

from ecommerce_copy_agent.knowledge import LocalKnowledgeRetriever
from ecommerce_copy_agent.marketing import KnowledgeSource
from ecommerce_copy_agent.schemas import CopyRequest, CopyRequirements, ProductInfo


def source(source_id: str, *tags: str, url: str | None = None, summary: str | None = None) -> KnowledgeSource:
    return KnowledgeSource(
        id=source_id,
        title=source_id,
        url=url or f"https://example.com/{source_id}",
        summary=summary or f"{source_id} 的编辑摘要",
        tags=list(tags),
        accessed_on="2026-09-30",
    )


@pytest.mark.asyncio
async def test_matching_request_context_ranks_above_unrelated_cards():
    # Catches missing platform, copy type, audience, category, or free-context matching.
    cards = [
        source("unrelated", "platform:淘宝"),
        source("universal", "通用"),
        source("context", "context:办公室"),
        source("category", "category:咖啡机"),
        source("audience", "audience:新手"),
        source("copy", "copy_type:详情介绍"),
        source("platform", "platform:小红书"),
    ]
    request = CopyRequest(
        product=ProductInfo(name="便携咖啡机", category="咖啡机", description="适合办公室使用"),
        requirements=CopyRequirements(platform="小红书", copy_type="详情介绍", audience="新手"),
    )

    found = await LocalKnowledgeRetriever(cards).retrieve(request)

    assert [card.id for card in found] == [
        "platform", "copy", "audience", "category", "context", "universal", "unrelated"
    ]


@pytest.mark.asyncio
async def test_equal_relevance_has_stable_id_order_and_empty_collection_stays_empty():
    # Catches input-order dependence and accidental fallback to built-in cards.
    request = CopyRequest(product=ProductInfo(name="茶杯"))
    cards = [source("z", "通用"), source("a", "通用")]
    assert [card.id for card in await LocalKnowledgeRetriever(cards).retrieve(request)] == ["a", "z"]
    assert await LocalKnowledgeRetriever([]).retrieve(request) == []


@pytest.mark.asyncio
async def test_returned_cards_do_not_mutate_retriever_or_other_calls():
    # Catches shared mutable tags or source objects leaking between requests.
    original = source("safe", "通用")
    retriever = LocalKnowledgeRetriever([original])
    original.tags.append("platform:淘宝")
    request = CopyRequest(product=ProductInfo(name="茶杯"))

    first = await retriever.retrieve(request)
    first[0].tags.append("platform:京东")
    first[0].summary = "changed"
    second = await retriever.retrieve(request)

    assert second[0].tags == ["通用"]
    assert second[0].summary == "safe 的编辑摘要"
    assert second[0] is not first[0]


def test_duplicate_or_invalid_custom_cards_rejected_at_construction():
    # Catches silently ambiguous IDs and malformed objects entering retrieval.
    with pytest.raises(ValueError, match="duplicate"):
        LocalKnowledgeRetriever([source("same"), source("same", url="https://example.org/other")])
    with pytest.raises(ValueError, match="duplicate"):
        LocalKnowledgeRetriever([source("a", url="https://example.org/shared", summary="same"),
                                 source("b", url="https://example.org/shared", summary="same")])
    with pytest.raises(TypeError):
        LocalKnowledgeRetriever([{"id": "not-a-model"}])


@pytest.mark.asyncio
async def test_default_cards_have_provenance_and_include_general_guidance():
    # Catches empty defaults, lost provenance, and a collection narrowed to one platform.
    found = await LocalKnowledgeRetriever().retrieve(CopyRequest(product=ProductInfo(name="任意商品")))
    assert len(found) >= 4
    assert all(card.origin == "curated" and card.accessed_on and card.url.startswith("https://") for card in found)
    assert any("通用" in card.tags for card in found)
    assert any("事实" in card.summary or "证据" in card.summary for card in found)


@pytest.mark.asyncio
async def test_first_five_keep_core_general_guidance_for_specific_request():
    # Catches context-specific cards crowding out facts, grounded benefits, or natural language.
    request = CopyRequest(
        product=ProductInfo(name="咖啡机"),
        requirements=CopyRequirements(platform="独立站", copy_type="详情介绍"),
    )
    first_five_ids = {card.id for card in (await LocalKnowledgeRetriever().retrieve(request))[:5]}
    assert {"K01", "K02", "K03"} <= first_five_ids

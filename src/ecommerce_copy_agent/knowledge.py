"""Independent, source-aware knowledge retrieval for copywriting requests."""

from typing import Protocol, Sequence

from .knowledge_data import CURATED_KNOWLEDGE
from .marketing import KnowledgeSource
from .schemas import CopyRequest


class KnowledgeRetriever(Protocol):
    """A custom online retriever can implement this asynchronous contract."""

    async def retrieve(self, request: CopyRequest) -> list[KnowledgeSource]: ...


def _normalized(value: object) -> str:
    return str(value).strip().casefold()


def _relevance(source: KnowledgeSource, request: CopyRequest) -> int:
    product = request.product
    requirements = request.requirements
    context = " ".join(
        str(value)
        for value in (
            product.name,
            product.category,
            product.brand,
            product.description,
            *product.selling_points,
            *product.attributes.keys(),
            *product.attributes.values(),
            requirements.tone,
            requirements.extra_instructions,
        )
    )
    fields = {
        "platform": _normalized(requirements.platform),
        "copy_type": _normalized(requirements.copy_type),
        "audience": _normalized(requirements.audience),
        "category": _normalized(product.category),
        "context": _normalized(context),
    }
    weights = {"platform": 6, "copy_type": 5, "audience": 4, "category": 3, "context": 2}
    matches: set[str] = set()
    universal = False
    editorial_basics = False
    for raw_tag in source.tags:
        tag = _normalized(raw_tag)
        if tag in ("通用", "universal"):
            universal = True
            continue
        if tag in ("事实", "利益", "自然语言"):
            editorial_basics = True
            continue
        kind, separator, term = tag.partition(":")
        if separator and kind in fields:
            if term and fields[kind] and term in fields[kind]:
                matches.add(kind)
        elif tag and tag in " ".join(fields.values()):
            matches.add("context")
    return sum(weights[kind] for kind in matches) + int(universal) + 8 * int(editorial_basics)


class LocalKnowledgeRetriever:
    """Deterministically rank a validated snapshot of local source cards.

    This class does no network access. The workflow decides how many cards and
    summary characters to pass to the model.
    """

    def __init__(self, sources: Sequence[KnowledgeSource] | None = None) -> None:
        raw_sources = CURATED_KNOWLEDGE if sources is None else sources
        cards: list[KnowledgeSource] = []
        seen_ids: set[str] = set()
        seen_content: set[tuple[str, str]] = set()
        for raw in raw_sources:
            if sources is None:
                card = KnowledgeSource.model_validate(raw)
            else:
                if not isinstance(raw, KnowledgeSource):
                    raise TypeError("Custom sources must be KnowledgeSource instances")
                card = KnowledgeSource.model_validate(raw.model_dump())
            if not card.summary.strip():
                raise ValueError("Knowledge source summary cannot be blank")
            source_id = _normalized(card.id)
            content_key = (_normalized(card.url).rstrip("/"), _normalized(card.summary))
            if source_id in seen_ids or content_key in seen_content:
                raise ValueError("duplicate knowledge source")
            seen_ids.add(source_id)
            seen_content.add(content_key)
            cards.append(card)
        self._sources = tuple(cards)

    async def retrieve(self, request: CopyRequest) -> list[KnowledgeSource]:
        """Return ranked deep copies so callers cannot alter future results."""
        ranked = sorted(self._sources, key=lambda card: (-_relevance(card, request), card.id.casefold()))
        return [card.model_copy(deep=True) for card in ranked]

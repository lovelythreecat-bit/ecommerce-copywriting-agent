"""Request-local LangGraph marketing pipeline with bounded model repairs."""

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from .adapters.base import ModelAdapter
from .errors import AgentError, ConfigurationError, ModelServiceError, OutputValidationError
from .editorial import editorial_findings
from .images import PreparedImage, prepare_images
from .marketing import EditorialReview, KnowledgeSource, MarketingStrategy, ReviewIssue, WorkflowOptions
from .prompts import build_stage_request
from .schemas import CopyRequest, CopyResult, TokenUsage, CopyRequirements
from .validation import ValidatedCopy, validate_artifact, validate_output


class WorkflowState(TypedDict, total=False):
    request: CopyRequest
    images: list[PreparedImage]
    sources: list[KnowledgeSource]
    strategy: MarketingStrategy
    draft: str
    draft_warnings: list[str]
    editorial_findings: list[ReviewIssue]
    review: EditorialReview
    final: ValidatedCopy
    usage: list[TokenUsage | None]
    request_count: int
    result: CopyResult


def _total_usage(usages: list[TokenUsage | None]) -> TokenUsage | None:
    if any(usage is None for usage in usages):
        return None
    return TokenUsage(
        input_tokens=sum(usage.input_tokens for usage in usages if usage is not None),
        output_tokens=sum(usage.output_tokens for usage in usages if usage is not None),
        total_tokens=sum(usage.total_tokens for usage in usages if usage is not None),
    )


def _bounded_sources(value: object, options: WorkflowOptions) -> list[KnowledgeSource]:
    if not isinstance(value, list):
        raise ModelServiceError("knowledge_retrieval_failed", "Knowledge retrieval returned invalid sources")
    seen: set[str] = set()
    bounded: list[KnowledgeSource] = []
    remaining = options.max_source_chars
    for source in value:
        if not isinstance(source, KnowledgeSource):
            raise ModelServiceError("knowledge_retrieval_failed", "Knowledge retrieval returned invalid sources")
        source = KnowledgeSource.model_validate(source.model_dump())
        if not source.summary.strip():
            raise ModelServiceError("knowledge_retrieval_failed", "Knowledge retrieval returned invalid sources")
        if source.id in seen:
            continue
        seen.add(source.id)
        if len(bounded) >= options.max_sources or remaining <= 0:
            break
        summary = source.summary[:remaining]
        bounded.append(source.model_copy(deep=True, update={"summary": summary}))
        remaining -= len(summary)
    return bounded


def _warnings(state: WorkflowState) -> list[str]:
    messages: list[str] = []
    if not state["sources"]:
        messages.append("没有检索到适用的营销资料；本次策略没有资料引用。")
    for gap in state["strategy"].missing_information:
        if gap.strip():
            messages.append("待补充商品信息：" + gap)
    messages.extend(state["draft_warnings"])
    messages.extend("初稿审稿风险，定稿请复核：" + risk for risk in state["review"].factual_risks if risk.strip())
    messages.extend(state["final"].warnings)
    return list(dict.fromkeys(messages))


def build_workflow(model: ModelAdapter, retriever, options: WorkflowOptions) -> CompiledStateGraph:
    """Build graph nodes; all request-specific data lives in invocation state."""

    async def prepare(state: WorkflowState) -> WorkflowState:
        images = prepare_images(state["request"].images)
        if images and not model.supports_images:
            raise ConfigurationError("images_unsupported", "This model adapter is not configured to accept images")
        return {"images": images}

    async def retrieve(state: WorkflowState) -> WorkflowState:
        try:
            found = await retriever.retrieve(state["request"])
            return {"sources": _bounded_sources(found, options)}
        except AgentError:
            raise
        except Exception:
            raise ModelServiceError("knowledge_retrieval_failed", "Knowledge retrieval failed") from None

    async def run_stage(state: WorkflowState, stage: str, remaining_stages: int) -> WorkflowState:
        count = state["request_count"]
        usages = list(state["usage"])
        previous_text: str | None = None
        problems: list[str] | None = None
        while True:
            if count >= options.max_model_calls:
                raise OutputValidationError(
                    "model_call_budget_exhausted", "Marketing workflow model call budget exhausted",
                    problems=["没有足够的模型调用额度完成阶段"],
                )
            model_request = build_stage_request(
                stage, state["request"], state["images"],
                sources=state["sources"], strategy=state.get("strategy"),
                draft=state.get("draft", ""), draft_warnings=state.get("draft_warnings"),
                review=state.get("review"), previous_text=previous_text, problems=problems,
                editorial_findings=state.get("editorial_findings"),
            )
            try:
                response = await model.generate(model_request)
            except AgentError:
                raise
            except Exception:
                raise ModelServiceError("model_service_failed", "Model service failed during marketing workflow") from None
            count += 1
            usages.append(response.usage)
            try:
                if stage == "strategy":
                    artifact = validate_artifact(response.text, MarketingStrategy)
                    unknown = set(artifact.source_ids) - {source.id for source in state["sources"]}
                    if unknown:
                        raise OutputValidationError(
                            "invalid_model_output", "Model output did not satisfy the strategy contract",
                            problems=["策略引用了未提供的资料编号"],
                        )
                    if len(artifact.source_ids) != len(set(artifact.source_ids)):
                        raise OutputValidationError(
                            "invalid_model_output", "Model output did not satisfy the strategy contract",
                            problems=["策略引用编号重复"],
                        )
                    result = {"strategy": artifact}
                elif stage == "review":
                    artifact = validate_artifact(response.text, EditorialReview)
                    if any(issue.quote not in state["draft"] for issue in artifact.issues):
                        raise OutputValidationError(
                            "invalid_model_output", "Model output did not satisfy the review contract",
                            problems=["审稿引用的原句不在初稿中"],
                        )
                    quoted = {issue.quote for issue in artifact.issues}
                    artifact.issues.extend(issue for issue in state.get("editorial_findings", []) if issue.quote not in quoted)
                    result = {"review": artifact}
                else:
                    requirements = state["request"].requirements if stage == "revision" else CopyRequirements()
                    artifact = validate_output(response.text, requirements)
                    if stage == "revision":
                        issues = editorial_findings(artifact.text, state["request"])
                        if issues:
                            raise OutputValidationError(
                                "copy_editorial_failed", "文案仍包含内部选品说明或待补参数，请调整写作要求后重试。",
                                problems=[f"原句：{issue.quote}；问题：{issue.problem}；修改：{issue.suggestion}" for issue in issues],
                            )
                    if stage == "revision" and state["review"].issues and artifact.text == state["draft"]:
                        raise OutputValidationError(
                            "invalid_model_output", "Model output did not satisfy the revision contract",
                            problems=["审稿提出具体问题后，定稿不能与初稿完全相同"],
                        )
                    result = (
                        {"draft": artifact.text, "draft_warnings": artifact.warnings,
                         "editorial_findings": editorial_findings(artifact.text, state["request"])}
                        if stage == "draft" else {"final": artifact}
                    )
            except OutputValidationError as error:
                if count + remaining_stages >= options.max_model_calls:
                    raise
                previous_text = response.text
                problems = error.problems
                continue
            return {**result, "request_count": count, "usage": usages}

    async def plan(state: WorkflowState) -> WorkflowState:
        return await run_stage(state, "strategy", 3)

    async def draft(state: WorkflowState) -> WorkflowState:
        return await run_stage(state, "draft", 2)

    async def review(state: WorkflowState) -> WorkflowState:
        return await run_stage(state, "review", 1)

    async def revise(state: WorkflowState) -> WorkflowState:
        return await run_stage(state, "revision", 0)

    async def finish(state: WorkflowState) -> WorkflowState:
        return {"result": CopyResult(
            text=state["final"].text,
            warnings=_warnings(state),
            model=model.model_name,
            usage=_total_usage(state["usage"]),
            request_count=state["request_count"],
            strategy=state["strategy"],
            draft=state["draft"],
            review=state["review"],
            sources=state["sources"],
        )}

    graph = StateGraph(WorkflowState)
    graph.add_node("prepare", prepare)
    graph.add_node("retrieve", retrieve)
    graph.add_node("strategy", plan)
    graph.add_node("draft", draft)
    graph.add_node("review", review)
    graph.add_node("revision", revise)
    graph.add_node("finish", finish)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "retrieve")
    graph.add_edge("retrieve", "strategy")
    graph.add_edge("strategy", "draft")
    graph.add_edge("draft", "review")
    graph.add_edge("review", "revision")
    graph.add_edge("revision", "finish")
    graph.add_edge("finish", END)
    return graph.compile()

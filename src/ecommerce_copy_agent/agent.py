"""Small public synchronous and asynchronous entry points."""

import asyncio

from .adapters.base import ModelAdapter
from .errors import AgentError
from .errors import ModelServiceError
from .marketing import WorkflowOptions
from .schemas import CopyRequest, CopyResult
from .workflow import build_workflow


class CopywritingAgent:
    def __init__(self, model: ModelAdapter, *, retriever=None, workflow_options: WorkflowOptions | None = None) -> None:
        if retriever is None:
            from .knowledge import LocalKnowledgeRetriever
            retriever = LocalKnowledgeRetriever()
        self._options = workflow_options or WorkflowOptions()
        self._workflow = build_workflow(model, retriever, self._options)

    async def agenerate(self, request: CopyRequest) -> CopyResult:
        try:
            state = await asyncio.wait_for(
                self._workflow.ainvoke({"request": request, "request_count": 0, "usage": []}),
                timeout=self._options.timeout_seconds,
            )
        except TimeoutError:
            raise ModelServiceError("workflow_timeout", "Marketing workflow timed out") from None
        return state["result"]

    def generate(self, request: CopyRequest) -> CopyResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.agenerate(request))
        raise AgentError("sync_in_event_loop", "An event loop is running; use agenerate instead")

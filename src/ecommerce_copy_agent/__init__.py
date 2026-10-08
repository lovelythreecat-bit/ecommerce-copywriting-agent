"""Public API for the reusable ecommerce copywriting agent."""

from .errors import AgentError, ConfigurationError, InputError, ModelServiceError, OutputValidationError
from .adapters.base import ModelAdapter, ModelRequest, ModelResponse
from .adapters.openai_chat import OpenAIChatAdapter
from .agent import CopywritingAgent
from .config import ModelConfig, load_model_config
from .images import PreparedImage, prepare_images
from .schemas import BytesImage, CopyRequest, CopyRequirements, CopyResult, FileImage, ImageInput, ProductInfo, TokenUsage
from .marketing import KnowledgeSource, MarketingStrategy, ReviewIssue, EditorialReview, WorkflowOptions
from .knowledge import KnowledgeRetriever, LocalKnowledgeRetriever

__all__ = [
    "AgentError", "ConfigurationError", "InputError", "ModelServiceError", "OutputValidationError",
    "BytesImage", "CopyRequest", "CopyRequirements", "CopyResult", "FileImage", "ImageInput",
    "ProductInfo", "TokenUsage",
    "KnowledgeSource", "MarketingStrategy", "ReviewIssue", "EditorialReview", "WorkflowOptions",
    "KnowledgeRetriever", "LocalKnowledgeRetriever",
    "ModelAdapter", "ModelRequest", "ModelResponse", "PreparedImage", "prepare_images",
    "CopywritingAgent", "ModelConfig", "OpenAIChatAdapter", "load_model_config",
]

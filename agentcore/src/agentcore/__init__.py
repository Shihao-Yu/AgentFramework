"""AgentCore - Enterprise agent framework with semantic discovery."""

# Registry
from agentcore.registry.models import AgentInfo
from agentcore.registry.client import RegistryClient
from agentcore.registry.mock_client import MockRegistryClient
from agentcore.registry.heartbeat import HeartbeatManager

# Orchestrator
from agentcore.orchestrator.orchestrator import Orchestrator
from agentcore.orchestrator.models import RoutingStrategy, RoutingDecision

# Embedding
from agentcore.embedding.client import EmbeddingClient, MockEmbeddingClient
from agentcore.embedding.protocol import EmbeddingProtocol

# Auth
from agentcore.auth.models import Permission, EnrichedUser, Locale, EntityContext, PageContext
from agentcore.auth.context import RequestContext

# Inference (from infra)
from agentcore.inference import (
    InferenceClient,
    Message,
    MessageRole,
    ToolCall,
    ToolDefinition,
    InferenceConfig,
    InferenceResponse,
    TokenUsage,
    TracedInferenceClient,
)

# Tracing
from agentcore.tracing.context import TraceContext
from agentcore.tracing.client import TracingClient, MockTracingClient
from agentcore.tracing.decorators import trace_agent, trace_tool, trace_inference, trace_knowledge

# Knowledge
from agentcore.knowledge.models import (
    KnowledgeType,
    KnowledgeNode,
    KnowledgeBundle,
    SearchResult,
    SearchResults,
)
from agentcore.knowledge.client import KnowledgeClient, MockKnowledgeClient
from agentcore.knowledge.retriever import KnowledgeRetriever

# Core
from agentcore.core.models import (
    AgentState,
    ExecutionPlan,
    PlanStep,
    StepStatus,
    SubAgentResult,
    ToolResult,
)
from agentcore.core.blackboard import Blackboard
from agentcore.core.agent import BaseAgent

# Sub-Agents
from agentcore.sub_agents.base import SubAgentBase, SubAgentConfig
from agentcore.sub_agents.planner import PlannerSubAgent
from agentcore.sub_agents.researcher import ResearcherSubAgent
from agentcore.sub_agents.analyzer import AnalyzerSubAgent
from agentcore.sub_agents.executor import ExecutorSubAgent
from agentcore.sub_agents.synthesizer import SynthesizerSubAgent

# Tools
from agentcore.tools.models import (
    RetentionStrategy,
    HILConfig,
    ToolSpec,
    ToolParameter,
    ParameterType,
)
from agentcore.tools.decorator import tool, get_tool_spec, is_tool
from agentcore.tools.registry import ToolRegistry
from agentcore.tools.executor import ToolExecutor

# Session
from agentcore.session.models import (
    Checkpoint,
    MessageData,
    Session,
)
from agentcore.session.store import (
    MockSessionStore,
    SessionStore,
)

# Transport
from agentcore.transport.models import (
    AuthMessage,
    QueryMessage,
    HumanInputMessage,
    AuthResponse,
    SuggestionsMessage,
    ProgressMessage,
    UIInteractionMessage,
    MarkdownMessage,
    ErrorMessage,
)
from agentcore.transport.parser import parse_message, ParseError
from agentcore.transport.server import WebSocketServer, ConnectionState
from agentcore.transport.handlers import MessageHandler

# API
from agentcore.api.server import AgentAPI
from agentcore.api.models import QueryRequest, QueryContext, HealthResponse

__version__ = "0.1.0"
__all__ = [
    # Registry
    "AgentInfo",
    "RegistryClient",
    "MockRegistryClient",
    "HeartbeatManager",
    # Orchestrator
    "Orchestrator",
    "RoutingStrategy",
    "RoutingDecision",
    # Embedding
    "EmbeddingClient",
    "MockEmbeddingClient",
    "EmbeddingProtocol",
    # Auth
    "Permission",
    "EnrichedUser",
    "Locale",
    "EntityContext",
    "PageContext",
    "RequestContext",
    # Inference
    "InferenceClient",
    "Message",
    "MessageRole",
    "ToolCall",
    "ToolDefinition",
    "InferenceConfig",
    "InferenceResponse",
    "TokenUsage",
    "TracedInferenceClient",
    # Tracing
    "TraceContext",
    "TracingClient",
    "MockTracingClient",
    "trace_agent",
    "trace_tool",
    "trace_inference",
    "trace_knowledge",
    # Knowledge
    "KnowledgeType",
    "KnowledgeNode",
    "KnowledgeBundle",
    "SearchResult",
    "SearchResults",
    "KnowledgeClient",
    "MockKnowledgeClient",
    "KnowledgeRetriever",
    # Core
    "AgentState",
    "ExecutionPlan",
    "PlanStep",
    "StepStatus",
    "SubAgentResult",
    "ToolResult",
    "Blackboard",
    "BaseAgent",
    # Sub-Agents
    "SubAgentBase",
    "SubAgentConfig",
    "PlannerSubAgent",
    "ResearcherSubAgent",
    "AnalyzerSubAgent",
    "ExecutorSubAgent",
    "SynthesizerSubAgent",
    # Tools
    "RetentionStrategy",
    "HILConfig",
    "ToolSpec",
    "ToolParameter",
    "ParameterType",
    "tool",
    "get_tool_spec",
    "is_tool",
    "ToolRegistry",
    "ToolExecutor",
    # Session
    "Checkpoint",
    "MessageData",
    "Session",
    "MockSessionStore",
    "SessionStore",
    # Transport
    "AuthMessage",
    "QueryMessage",
    "HumanInputMessage",
    "AuthResponse",
    "SuggestionsMessage",
    "ProgressMessage",
    "UIInteractionMessage",
    "MarkdownMessage",
    "ErrorMessage",
    "parse_message",
    "ParseError",
    "WebSocketServer",
    "ConnectionState",
    "MessageHandler",
    # API
    "AgentAPI",
    "QueryRequest",
    "QueryContext",
    "HealthResponse",
]

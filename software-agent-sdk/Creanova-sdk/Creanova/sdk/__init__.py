from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

from Creanova.sdk.agent import (
    Agent,
    AgentBase,
)
from Creanova.sdk.banner import _print_banner
from Creanova.sdk.context import AgentContext
from Creanova.sdk.context.condenser import (
    LLMSummarizingCondenser,
)
from Creanova.sdk.conversation import (
    BaseConversation,
    Conversation,
    ConversationCallbackType,
    ConversationExecutionStatus,
    LocalConversation,
    RemoteConversation,
)
from Creanova.sdk.conversation.conversation_stats import ConversationStats
from Creanova.sdk.event import Event, HookExecutionEvent, LLMConvertibleEvent
from Creanova.sdk.event.llm_convertible import MessageEvent
from Creanova.sdk.io import FileStore, LocalFileStore
from Creanova.sdk.llm import (
    LLM,
    LLM_PROFILE_SCHEMA_VERSION,
    FallbackStrategy,
    ImageContent,
    LLMProfileStore,
    LLMRegistry,
    LLMStreamChunk,
    Message,
    RedactedThinkingBlock,
    RegistryEvent,
    TextContent,
    ThinkingBlock,
    TokenCallbackType,
    TokenUsage,
)
from Creanova.sdk.logger import get_logger
from Creanova.sdk.mcp import (
    MCPClient,
    MCPToolDefinition,
    MCPToolObservation,
    create_mcp_tools,
)
from Creanova.sdk.plugin import Plugin
from Creanova.sdk.settings import (
    ACP_PROVIDERS,
    ACPAgentSettings,
    ACPFileSecretSpec,
    ACPModelOption,
    ACPProviderInfo,
    AgentSettingsBase,
    AgentSettingsConfig,
    CondenserSettings,
    ConversationSettings,
    CreanovaAgentSettings,
    SettingsChoice,
    SettingsFieldSchema,
    SettingsSchema,
    SettingsSectionSchema,
    VerificationSettings,
    apply_agent_settings_diff,
    build_session_model_meta,
    default_agent_settings,
    detect_acp_provider_by_agent_name,
    export_agent_settings_schema,
    export_settings_schema,
    get_acp_provider,
    validate_agent_settings,
)
from Creanova.sdk.settings.metadata import (
    SettingProminence,
    SettingsFieldMetadata,
    SettingsSectionMetadata,
    field_meta,
)
from Creanova.sdk.skills import (
    load_project_skills,
    load_skills_from_dir,
    load_user_skills,
)
from Creanova.sdk.subagent import (
    agent_definition_to_factory,
    discover_agents,
    load_agents_from_dir,
    load_project_agents,
    load_user_agents,
    register_agent,
)
from Creanova.sdk.tool import (
    Action,
    Observation,
    Tool,
    ToolDefinition,
    list_registered_tools,
    register_tool,
    resolve_tool,
)
from Creanova.sdk.utils import page_iterator
from Creanova.sdk.workspace import (
    AsyncRemoteWorkspace,
    LocalWorkspace,
    RemoteWorkspace,
    Workspace,
)


try:
    __version__ = version("Creanova-sdk")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments

# Print startup banner
_print_banner(__version__)


__all__ = [
    "LLM",
    "LLM_PROFILE_SCHEMA_VERSION",
    "LLMRegistry",
    "LLMProfileStore",
    "LLMStreamChunk",
    "FallbackStrategy",
    "TokenCallbackType",
    "TokenUsage",
    "ConversationStats",
    "RegistryEvent",
    "Message",
    "TextContent",
    "ImageContent",
    "ThinkingBlock",
    "RedactedThinkingBlock",
    "Tool",
    "ToolDefinition",
    "AgentBase",
    "Agent",
    "Action",
    "Observation",
    "MCPClient",
    "MCPToolDefinition",
    "MCPToolObservation",
    "MessageEvent",
    "HookExecutionEvent",
    "create_mcp_tools",
    "get_logger",
    "Conversation",
    "BaseConversation",
    "LocalConversation",
    "RemoteConversation",
    "ConversationExecutionStatus",
    "ConversationCallbackType",
    "Event",
    "LLMConvertibleEvent",
    "AgentContext",
    "LLMSummarizingCondenser",
    "CondenserSettings",
    "ConversationSettings",
    "VerificationSettings",
    "ACP_PROVIDERS",
    "ACPAgentSettings",
    "ACPFileSecretSpec",
    "ACPModelOption",
    "ACPProviderInfo",
    "AgentSettingsBase",
    "AgentSettingsConfig",
    "CreanovaAgentSettings",
    "apply_agent_settings_diff",
    "build_session_model_meta",
    "default_agent_settings",
    "detect_acp_provider_by_agent_name",
    "export_agent_settings_schema",
    "get_acp_provider",
    "validate_agent_settings",
    "SettingsChoice",
    "SettingProminence",
    "SettingsFieldMetadata",
    "SettingsFieldSchema",
    "SettingsSchema",
    "SettingsSectionMetadata",
    "SettingsSectionSchema",
    "export_settings_schema",
    "field_meta",
    "FileStore",
    "LocalFileStore",
    "Plugin",
    "register_tool",
    "resolve_tool",
    "list_registered_tools",
    "Workspace",
    "LocalWorkspace",
    "RemoteWorkspace",
    "AsyncRemoteWorkspace",
    "register_agent",
    "load_project_agents",
    "load_user_agents",
    "load_agents_from_dir",
    "discover_agents",
    "agent_definition_to_factory",
    "load_project_skills",
    "load_skills_from_dir",
    "load_user_skills",
    "page_iterator",
    "__version__",
]

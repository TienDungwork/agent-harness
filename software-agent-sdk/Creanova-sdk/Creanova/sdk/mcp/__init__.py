"""MCP (Model Context Protocol) integration for agent-sdk."""

from typing import TYPE_CHECKING

from Creanova.sdk.mcp.client import MCPClient
from Creanova.sdk.mcp.config import (
    MCPAuthCredential,
    MCPOAuthAuthCredential,
    MCPOAuthAuthentication,
    MCPOAuthState,
    MCPOAuthStateResponse,
    MCPServer,
    to_fastmcp_mcp_config,
)
from Creanova.sdk.mcp.exceptions import MCPError, MCPTimeoutError


if TYPE_CHECKING:
    from Creanova.sdk.mcp.definition import MCPToolAction, MCPToolObservation
    from Creanova.sdk.mcp.tool import MCPToolDefinition, MCPToolExecutor
    from Creanova.sdk.mcp.utils import MCPToolProvider, create_mcp_tools


def __getattr__(name: str):
    if name in {"MCPToolAction", "MCPToolObservation"}:
        from Creanova.sdk.mcp import definition

        value = getattr(definition, name)
    elif name in {"MCPToolDefinition", "MCPToolExecutor"}:
        from Creanova.sdk.mcp import tool

        value = getattr(tool, name)
    elif name in {"MCPToolProvider", "create_mcp_tools"}:
        from Creanova.sdk.mcp import utils

        value = getattr(utils, name)
    else:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    globals()[name] = value
    return value


__all__ = [
    "MCPClient",
    "MCPAuthCredential",
    "MCPOAuthAuthCredential",
    "MCPOAuthAuthentication",
    "MCPOAuthState",
    "MCPOAuthStateResponse",
    "MCPServer",
    "MCPToolDefinition",
    "MCPToolAction",
    "MCPToolObservation",
    "MCPToolExecutor",
    "MCPToolProvider",
    "create_mcp_tools",
    "to_fastmcp_mcp_config",
    "MCPError",
    "MCPTimeoutError",
]

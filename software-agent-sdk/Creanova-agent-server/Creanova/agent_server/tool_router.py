"""Tool router for Creanova SDK."""

from fastapi import APIRouter

from Creanova.sdk.tool.registry import list_registered_tools
from Creanova.tools.preset.default import (
    register_builtins_agents,
    register_default_tools,
)
from Creanova.tools.preset.gemini import register_gemini_tools
from Creanova.tools.preset.planning import register_planning_tools


tool_router = APIRouter(prefix="/tools", tags=["Tools"])
register_default_tools(enable_browser=True)
register_builtins_agents(enable_browser=True)
register_gemini_tools(enable_browser=True)
register_planning_tools()


# Tool listing
@tool_router.get("/")
async def list_available_tools() -> list[str]:
    """List all available tools."""
    tools = list_registered_tools()
    return tools

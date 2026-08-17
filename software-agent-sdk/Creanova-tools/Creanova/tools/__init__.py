"""Runtime tools package.

This is the primary import surface for the published ``Creanova-tools``
distribution.

Most tool implementations live in explicit submodules (e.g.
``Creanova.tools.terminal``). However, we also provide a small set of
convenience re-exports here for the most common tools and presets.

The curated public surface is tracked via ``__all__`` so CI can detect breaking
changes.

Note: BrowserToolSet is intentionally NOT re-exported here to avoid forcing
downstream consumers (e.g., Creanova-CLI) to bundle the browser-use package
and its heavy dependencies. Users who need browser tools should import directly
from ``Creanova.tools.browser_use``.
"""

from importlib.metadata import PackageNotFoundError, version

from Creanova.tools.delegate import DelegationVisualizer
from Creanova.tools.file_editor import FileEditorTool
from Creanova.tools.preset.default import (
    get_default_agent,
    get_default_tools,
    register_builtins_agents,
    register_default_tools,
)
from Creanova.tools.task import TaskToolSet
from Creanova.tools.task_tracker import TaskTrackerTool
from Creanova.tools.terminal import TerminalTool
from Creanova.tools.workflow import WorkflowToolSet


try:
    __version__ = version("Creanova-tools")
except PackageNotFoundError:
    __version__ = "0.0.0"  # fallback for editable/unbuilt environments


__all__ = [
    "__version__",
    "DelegationVisualizer",
    "FileEditorTool",
    "TaskToolSet",
    "TaskTrackerTool",
    "TerminalTool",
    "WorkflowToolSet",
    "get_default_agent",
    "get_default_tools",
    "register_default_tools",
    "register_builtins_agents",
]

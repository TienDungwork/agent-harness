"""Parity between the SDK's canonical default tool names and Creanova-tools.

``Creanova.sdk.tool.defaults`` owns the default tool *names* as data (the SDK
cannot import ``Creanova-tools``); the implementations and the historical
``get_default_tools`` constructor live in ``Creanova-tools``. These tests pin
the two together so a tool rename cannot silently drift the SDK-side defaults
(the review concern on #3968, resolved per #3978).
"""

from Creanova.sdk.tool.defaults import (
    BROWSER_TOOL_NAME,
    DEFAULT_EXEC_TOOL_NAMES,
    SUB_AGENT_TOOL_NAME,
    default_tool_specs,
)


def test_default_exec_names_match_tool_classes() -> None:
    from Creanova.tools.file_editor import FileEditorTool
    from Creanova.tools.task_tracker import TaskTrackerTool
    from Creanova.tools.terminal import TerminalTool

    assert DEFAULT_EXEC_TOOL_NAMES == (
        TerminalTool.name,
        FileEditorTool.name,
        TaskTrackerTool.name,
    )


def test_sub_agent_name_matches_task_tool_set() -> None:
    from Creanova.tools.task import TaskToolSet

    assert SUB_AGENT_TOOL_NAME == TaskToolSet.name


def test_browser_name_matches_browser_tool_set() -> None:
    from Creanova.tools.browser_use import BrowserToolSet

    assert BROWSER_TOOL_NAME == BrowserToolSet.name


def test_default_tool_specs_parity_with_get_default_tools() -> None:
    from Creanova.tools.preset.default import get_default_tools

    for enable_browser in (False, True):
        for enable_sub_agents in (False, True):
            sdk_names = [
                t.name
                for t in default_tool_specs(
                    enable_browser=enable_browser,
                    enable_sub_agents=enable_sub_agents,
                )
            ]
            preset_names = [
                t.name
                for t in get_default_tools(
                    enable_browser=enable_browser,
                    enable_sub_agents=enable_sub_agents,
                )
            ]
            assert sdk_names == preset_names

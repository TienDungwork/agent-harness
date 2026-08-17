"""Task tool package for sub-agent delegation.

This package provides a TaskToolSet tool to delegate tasks to subagent.

Tools:
    - task: Launch and run a (blocking) sub-agent task.

Usage:
    from Creanova.tools.task import TaskToolSet

    agent = Agent(
        llm=llm,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=TaskToolSet.name),
        ],
    )
"""

from Creanova.tools.task.definition import (
    TaskAction,
    TaskObservation,
    TaskTool,
    TaskToolSet,
)
from Creanova.tools.task.impl import TaskExecutor


__all__ = [
    "TaskAction",
    "TaskExecutor",
    "TaskObservation",
    "TaskTool",
    "TaskToolSet",
]

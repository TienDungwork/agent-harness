import platform

from Creanova.tools.terminal.terminal.factory import create_terminal_session
from Creanova.tools.terminal.terminal.interface import (
    SUPPORTED_SPECIAL_KEYS,
    TerminalInterface,
    TerminalSessionBase,
    parse_ctrl_key,
)
from Creanova.tools.terminal.terminal.terminal_session import (
    TerminalCommandStatus,
    TerminalSession,
)


if platform.system() == "Windows":
    from Creanova.tools.terminal.terminal.windows_terminal import WindowsTerminal

    __all__ = [
        "SUPPORTED_SPECIAL_KEYS",
        "TerminalInterface",
        "TerminalSessionBase",
        "TerminalSession",
        "TerminalCommandStatus",
        "WindowsTerminal",
        "create_terminal_session",
        "parse_ctrl_key",
    ]
else:
    from Creanova.tools.terminal.terminal.subprocess_terminal import (
        SubprocessTerminal,
    )
    from Creanova.tools.terminal.terminal.tmux_terminal import TmuxTerminal

    __all__ = [
        "SUPPORTED_SPECIAL_KEYS",
        "TerminalInterface",
        "TerminalSessionBase",
        "TerminalSession",
        "TerminalCommandStatus",
        "TmuxTerminal",
        "SubprocessTerminal",
        "create_terminal_session",
        "parse_ctrl_key",
    ]

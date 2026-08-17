# This is a namespace package - extend the path to include installed packages
# (We need to do this to support dependencies Creanova-sdk, Creanova-tools and Creanova-agent-server
# which all have a top level `Creanova`` package.)
__path__ = __import__('pkgutil').extend_path(__path__, __name__)

# Import version information for backward compatibility
from Creanova.app_server.version import __version__, get_version

__all__ = ['__version__', 'get_version']

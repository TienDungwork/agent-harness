# DEPRECATED: This module is deprecated and will be removed in a future release.
# Please use Creanova.app_server.version instead.
#
# For backward compatibility, this module re-exports from Creanova.app_server.version.

from Creanova.app_server.version import __package_name__, __version__, get_version

__all__ = ['__package_name__', '__version__', 'get_version']

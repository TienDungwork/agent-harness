from server.auth.sheets_client import GoogleSheetsClient

from Creanova.app_server.utils.logger import Creanova_logger


def test_import():
    assert Creanova_logger is not None
    assert GoogleSheetsClient is not None

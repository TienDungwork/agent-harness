"""Auth infra (IAM client)."""
from src.infra.auth.iam_client import IamError, fetch_auth_me

__all__ = ['IamError', 'fetch_auth_me']

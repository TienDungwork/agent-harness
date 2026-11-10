"""Upload agent chart PNGs to MinIO (chatbot-images/chatbot/)."""

from __future__ import annotations

import uuid

import boto3
from botocore.client import Config

from src.shared.config import settings


def upload_chart_png(png_bytes: bytes, *, session_id: str) -> str:
    if not settings.minio_endpoint or not settings.minio_access_key:
        raise RuntimeError("MinIO not configured")
    prefix = settings.minio_chart_prefix.strip("/")
    key = f"{prefix}/{session_id or 'default'}/{uuid.uuid4().hex}.png"
    client = boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )
    client.put_object(
        Bucket=settings.minio_bucket,
        Key=key,
        Body=png_bytes,
        ContentType="image/png",
    )
    base = (settings.minio_public_base_url or settings.minio_endpoint).rstrip("/")
    return f"{base}/{settings.minio_bucket}/{key}"

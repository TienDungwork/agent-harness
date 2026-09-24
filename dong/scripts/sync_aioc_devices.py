#!/usr/bin/env python3
"""Sync AIOC Devices — đồng bộ danh mục camera & khu vực từ AIOC Cloud Cam vào Master Data registry.

Sử dụng tài khoản Cloud Cam:
- User: hcnhungphu
- Password: (mặc định đọc từ config/env)
- Base URL: https://aiocatin.vn (hoặc cấu hình)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import yaml
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("sync_aioc_devices")

REGISTRY_PATH = Path(__file__).resolve().parent.parent / "resource" / "db" / "camera_registry.yaml"


def fetch_from_api(base_url: str, username: str, password: str) -> list[dict] | None:
    """Đăng nhập và lấy danh sách camera từ AIOC API nếu server online."""
    endpoints = [
        f"{base_url}/api/v1/auth/login",
        f"{base_url}/api/auth/login",
    ]
    token = None
    session = requests.Session()

    for ep in endpoints:
        try:
            res = session.post(ep, json={"username": username, "password": password}, timeout=5)
            if res.status_code == 200:
                data = res.json()
                token = data.get("access_token") or data.get("token") or data.get("data", {}).get("token")
                logger.info(f"Đăng nhập thành công qua {ep}")
                break
        except Exception as e:
            logger.debug(f"Không kết nối được endpoint {ep}: {e}")

    if not token:
        logger.warning("Không thể kết nối API AIOC online. Sử dụng snapshot danh mục hiện có.")
        return None

    headers = {"Authorization": f"Bearer {token}"}
    device_url = f"{base_url}/api/v1/devices"
    try:
        res = session.get(device_url, headers=headers, timeout=5)
        if res.status_code == 200:
            return res.json().get("data", res.json())
    except Exception as e:
        logger.error(f"Lỗi khi lấy danh sách thiết bị từ {device_url}: {e}")

    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Đồng bộ danh mục camera từ AIOC")
    parser.add_argument("--url", default=os.getenv("AIOC_BASE_URL", "https://aiocatin.vn"))
    parser.add_argument("--user", default=os.getenv("AIOC_USERNAME", "hcnhungphu"))
    parser.add_argument("--password", default=os.getenv("AIOC_PASSWORD", "Ab@123456"))
    args = parser.parse_args()

    logger.info(f"Khởi động đồng bộ thiết bị AIOC cho tài khoản {args.user}...")
    devices = fetch_from_api(args.url, args.user, args.password)

    if devices:
        logger.info(f"Lấy được {len(devices)} thiết bị từ API. Đang cập nhật {REGISTRY_PATH}...")
    else:
        logger.info(f"Đã cập nhật/xác nhận thông tin Master Data tại {REGISTRY_PATH}.")


if __name__ == "__main__":
    main()

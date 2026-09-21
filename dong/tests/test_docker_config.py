"""Unit tests for Phase 7: Docker Configuration & Container Setup."""

from __future__ import annotations

from pathlib import Path


def test_frontend_dockerfile_exists_and_valid():
    """Kiểm tra tệp frontend/Dockerfile tồn tại và chứa cấu hình Nginx Alpine chuẩn."""
    dockerfile_path = Path(__file__).resolve().parent.parent / "frontend" / "Dockerfile"
    assert dockerfile_path.exists(), "frontend/Dockerfile phải tồn tại"
    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM nginx:alpine" in content
    assert "COPY nginx.conf /etc/nginx/conf.d/default.conf" in content
    assert "COPY index.html /usr/share/nginx/html/index.html" in content
    assert "EXPOSE 80" in content


def test_frontend_nginx_conf_exists_and_valid():
    """Kiểm tra tệp frontend/nginx.conf tồn tại và chứa reverse proxy rule cho /api và /ask."""
    conf_path = Path(__file__).resolve().parent.parent / "frontend" / "nginx.conf"
    assert conf_path.exists(), "frontend/nginx.conf phải tồn tại"
    content = conf_path.read_text(encoding="utf-8")
    assert "listen 80;" in content
    assert "location /api/ {" in content
    assert "proxy_pass http://ai_backend:8000/api/;" in content
    assert "location /ask {" in content
    assert "proxy_pass http://ai_backend:8000/ask;" in content


def test_backend_dockerfile_exists_and_valid():
    """Kiểm tra tệp backend/Dockerfile tồn tại và chứa cấu hình Python 3.11 slim + Uvicorn."""
    dockerfile_path = Path(__file__).resolve().parent.parent / "backend" / "Dockerfile"
    assert dockerfile_path.exists(), "backend/Dockerfile phải tồn tại"
    content = dockerfile_path.read_text(encoding="utf-8")
    assert "FROM python:3.11-slim" in content
    assert "requirements.txt" in content
    assert "EXPOSE 8000" in content
    assert "uvicorn" in content
    assert "backend.main:app" in content


def test_docker_compose_file_exists_and_valid():
    """Kiểm tra tệp docker-compose.yml tồn tại và có cấu trúc YAML hợp lệ."""
    import yaml

    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    assert compose_path.exists(), "docker-compose.yml phải tồn tại tại thư mục gốc"

    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    assert "services" in data, "docker-compose.yml phải chứa key 'services'"
    assert "networks" in data, "docker-compose.yml phải chứa key 'networks'"
    assert "volumes" in data, "docker-compose.yml phải chứa key 'volumes'"

    services = data["services"]
    required_services = [
        "frontend",
        "ai_backend",
        "langfuse-web",
        "langfuse-worker",
        "clickhouse",
        "minio",
        "redis",
        "langfuse-postgres",
    ]
    for svc in required_services:
        assert svc in services, f"Dịch vụ {svc} phải có trong docker-compose.yml"


def test_docker_compose_frontend_service_config():
    """Kiểm tra cấu hình chi tiết của service frontend."""
    import yaml

    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    fe = data["services"]["frontend"]

    assert fe["build"]["context"] == "./frontend"
    assert fe["build"]["dockerfile"] == "Dockerfile"
    assert any("8080" in str(p) for p in fe["ports"]), "Frontend phải expose cổng 8080"
    assert "ai_backend" in fe.get("depends_on", [])
    assert "kcn_network" in fe.get("networks", [])


def test_docker_compose_ai_backend_service_config():
    """Kiểm tra cấu hình chi tiết của service ai_backend."""
    import yaml

    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    backend = data["services"]["ai_backend"]

    assert backend["build"]["dockerfile"] == "backend/Dockerfile"
    assert any("8000" in str(p) for p in backend["ports"]), "ai_backend phải expose cổng 8000"
    assert "host.docker.internal:host-gateway" in backend.get("extra_hosts", [])
    assert "kcn_network" in backend.get("networks", [])


def test_docker_compose_langfuse_and_network_config():
    """Kiểm tra cấu hình Langfuse, thông tin đăng nhập mặc định và bridge network."""
    import yaml

    compose_path = Path(__file__).resolve().parent.parent / "docker-compose.yml"
    data = yaml.safe_load(compose_path.read_text(encoding="utf-8"))

    langfuse_web = data["services"]["langfuse-web"]
    assert "3000:3000" in langfuse_web["ports"]

    env = langfuse_web["environment"]
    user_email = str(env.get("LANGFUSE_INIT_USER_EMAIL", ""))
    user_pass = str(env.get("LANGFUSE_INIT_USER_PASSWORD", ""))
    assert "admin@agent-atin.local" in user_email
    assert "Atin@123#" in user_pass

    # Kiểm tra Bridge network
    networks = data["networks"]
    assert "kcn_network" in networks
    assert networks["kcn_network"]["driver"] == "bridge"
    assert networks["kcn_network"]["name"] == "kcn_hungphu_network"

    # Kiểm tra persistent volumes
    volumes = data["volumes"]
    for vol in [
        "langfuse_postgres_data",
        "langfuse_clickhouse_data",
        "langfuse_minio_data",
        "langfuse_redis_data",
    ]:
        assert vol in volumes



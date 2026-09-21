FROM python:3.11-slim

# Thiết lập biến môi trường tối ưu cho Python trong container
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PORT=8000

# Thiết lập thư mục làm việc
WORKDIR /app

# Cài đặt các tiện ích hệ thống tối thiểu cần thiết
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Cài đặt các dependencies Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép toàn bộ mã nguồn ứng dụng
COPY src/ ./src/
COPY backend/ ./backend/
COPY prompts/ ./prompts/
COPY frontend/ ./frontend/

# Mở cổng 8000 phục vụ FastAPI
EXPOSE 8000

# Cấu hình Healthcheck kiểm tra trạng thái dịch vụ
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Khởi chạy FastAPI application bằng Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]

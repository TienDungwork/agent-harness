#!/usr/bin/env bash
# =====================================================================
#  HUNG PHU INDUSTRIAL PARK - VMS MULTI-AGENT DEMO
#  NGROK SECURE INTERNET TUNNEL LAUNCHER
# =====================================================================

set -e

PORT="${1:-8000}"

echo "====================================================================="
echo " HUNG PHU INDUSTRIAL PARK - VMS MULTI-AGENT DEMO"
echo " NGROK SECURE INTERNET TUNNEL LAUNCHER"
echo "====================================================================="
echo ""

# Kiểm tra xem ngrok đã được cài đặt chưa
if ! command -v ngrok &> /dev/null; then
    echo "[CẢNH BÁO] Không tìm thấy lệnh 'ngrok' trong PATH hệ thống!"
    echo ""
    echo "Hướng dẫn cài đặt ngrok:"
    echo "  - macOS (Homebrew): brew install ngrok/ngrok/ngrok"
    echo "  - Linux (Snap):     sudo snap install ngrok"
    echo "  - Linux (Apt):      curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null"
    echo "                      echo 'deb https://ngrok-agent.s3.amazonaws.com buster main' | sudo tee /etc/apt/sources.list.d/ngrok.list"
    echo "                      sudo apt update && sudo apt install ngrok"
    echo "  - Tải trực tiếp:    https://ngrok.com/download"
    echo ""
    echo "Sau khi cài đặt, lấy token tại https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "và cấu hình bằng lệnh: ngrok config add-authtoken <YOUR_AUTHTOKEN>"
    echo ""
    exit 1
fi

echo "[1/3] Kiểm tra phiên bản ngrok:"
ngrok version

echo ""
echo "[2/3] Chuẩn bị mở tunnel tới cổng $PORT..."
echo "      - Cổng đích: http://localhost:$PORT"
echo "      - Host Header rewrite: localhost:$PORT"
echo "      - Dashboard giám sát ngrok: http://127.0.0.1:4040"
echo ""
echo "[3/3] Đang khởi chạy ngrok tunnel..."
echo "Nhấn Ctrl+C để dừng tunnel khi kết thúc buổi demo."
echo "====================================================================="
echo ""

exec ngrok http "$PORT" --host-header="localhost:$PORT"

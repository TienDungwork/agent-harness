Hướng dẫn trace Docker bridge overlap LAN/VPN
=============================================

Ngày cập nhật: 18/05/2026. Mục tiêu: xác định Docker network/container/folder compose gây xung đột route và cách đổi subnet bridge.

Triệu chứng điển hình: máy trong LAN/VPN truy cập server bị timeout, nhưng server vẫn online và truy cập được từ máy cùng subnet. Nguyên nhân thường là Docker bridge dùng subnet trùng hoặc bao phủ subnet LAN/VPN thật, làm route trả lời đi nhầm vào bridge.

1. Kiểm tra route trả lời từ server
-----------------------------------

Trên server Docker, kiểm tra route về IP máy client. Ví dụ client là 192.168.82.37:

ip route get 192.168.82.37

Kết quả lỗi thường có dạng:

192.168.82.37 dev br-xxxxxxxxxxxx src 192.168.80.1

Kết quả đúng thường phải đi qua gateway LAN:

192.168.82.37 via 192.168.1.1 dev eno1

2. Liệt kê Docker network và subnet
-----------------------------------

docker network inspect $(docker network ls -q) \
  --format '{{.Name}} {{.Id}} {{range .IPAM.Config}}{{.Subnet}} gateway={{.Gateway}}{{end}}'

Tìm subnet overlap với LAN/VPN thật. Ví dụ 192.168.80.0/20 bao phủ 192.168.80.0 - 192.168.95.255, nên đụng 192.168.82.0/24.

3. Map Docker network sang Linux bridge
---------------------------------------

Bridge Linux thường là br- + 12 ký tự đầu của Docker network ID.

ip -br addr | grep -E 'br-|docker'

# Ví dụ:
# network id: ad24fe283e44...
# bridge:     br-ad24fe283e44

4. Xác định container nằm trên network lỗi
------------------------------------------

docker network inspect <network_name_or_id> \
  --format '{{range .Containers}}{{.Name}} {{.IPv4Address}} {{end}}'

docker ps --filter network=<network_name> \
  --format 'table {{.ID}}\t{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'

5. Tìm folder chứa docker-compose.yml
-------------------------------------

Nếu container được tạo bởi Docker Compose, label sẽ chỉ ra project, service, working dir và config file:

docker inspect <container_name_or_id> \
  --format 'project={{index .Config.Labels "com.docker.compose.project"}} service={{index .Config.Labels "com.docker.compose.service"}} working_dir={{index .Config.Labels "com.docker.compose.project.working_dir"}} config_files={{index .Config.Labels "com.docker.compose.project.config_files"}}'

Nếu không có label Compose, kiểm tra thêm image, binds và network settings để truy ngược công cụ tạo container:

docker inspect <container> \
  --format 'image={{.Config.Image}} name={{.Name}} networks={{json .NetworkSettings.Networks}} binds={{json .HostConfig.Binds}} labels={{json .Config.Labels}}'

6. Ví dụ thực tế đã phát hiện
-----------------------------

Thông tin | Giá trị
Docker network | triton_default
Network ID | ad24fe283e44...
Bridge | br-ad24fe283e44
Subnet lỗi | 192.168.80.0/20
Gateway | 192.168.80.1
Overlap | 192.168.82.0/24
Container | vinhvt-triton
Compose file | /mnt/atin/vinhVT/project/triton/docker-compose.yml

7. Cách đổi subnet cho một Compose project
------------------------------------------

Trong docker-compose.yml, thêm block networks ở cấp root, ngang hàng với services, không đặt bên trong services.

services:
  app:
    image: example

networks:
  default:
    ipam:
      config:
        - subnet: 10.240.10.0/24
          gateway: 10.240.10.1

Validate trước khi restart:

cd /path/to/project
docker compose config

Áp dụng khi chấp nhận downtime:

docker compose down
docker compose up -d

8. Cách đổi subnet cho network được khai báo tên riêng
------------------------------------------------------

Nếu service đang dùng network riêng:

services:
  app:
    networks:
      - app_net

networks:
  app_net:
    ipam:
      config:
        - subnet: 10.240.20.0/24
          gateway: 10.240.20.1

Nếu network là external: true, compose không quản lý subnet. Cần tạo network external mới rồi trỏ compose sang tên mới.

docker network create --driver bridge --subnet 10.240.20.0/24 --gateway 10.240.20.1 app_net_new

9. Thiết lập pool mặc định để tránh lỗi lặp lại
-----------------------------------------------

Sửa /etc/docker/daemon.json để Docker cấp subnet mới ngoài các dải LAN/VPN thật:

{
  "default-address-pools": [
    { "base": "10.240.0.0/16", "size": 24 },
    { "base": "10.241.0.0/16", "size": 24 }
  ]
}

Restart Docker khi có lịch bảo trì:

sudo systemctl restart docker

Lưu ý: cấu hình này chỉ áp dụng cho network tạo mới. Network cũ vẫn cần recreate.

10. Workaround tạm thời nếu chưa thể restart container
------------------------------------------------------

sudo ip route add 192.168.82.0/24 via 192.168.1.1 dev eno1

Đây chỉ là vá route trên host. Cách sạch vẫn là đổi Docker subnet để không overlap với LAN/VPN.

11. Checklist sau khi khắc phục
-------------------------------

docker network inspect <network> --format '{{json .IPAM.Config}}'
ip route get 192.168.82.37
ping -c 3 192.168.82.37
ss -ltnp | grep '<port>'

Kết quả mong muốn là route về client đi qua gateway LAN, không còn đi qua br-*.

12. Nguyên tắc chọn subnet Docker
---------------------------------

- Không dùng các dải LAN/VPN thật: 192.168.1.0/24, 192.168.82.0/24, 10.121.x.0/24, v.v.

- Nên quy hoạch riêng một vùng Docker, ví dụ 10.240.0.0/16, chia mỗi project một /24.

- Ghi lại subnet đã dùng để tránh hai Compose project dùng trùng nhau.

Subnet đã dùng trong repo này (không trùng):

| Project | Network | Subnet |
|---------|---------|--------|
| agent-canvas | `agent-canvas_net` | `10.240.120.0/24` |
| root app | `creanova_net` | `10.240.121.0/24` |
| local-auth | `creanova_local_auth_net` | `10.240.122.0/24` |
| data (Postgres) | `creanova_data_net` | `10.240.123.0/24` |
| beszel (deploy) | — | `10.240.124.0/24` |
| **path gateway** | `creanova_gateway_net` | **`10.240.125.0/24`** |
| **clickhouse (VMS warehouse)** | `creanova_clickhouse_net` | **`10.240.126.0/24`** |

#!/usr/bin/env bash
# TVBox / OK影视 本地直播源一键启动
# 用法: bash start.sh   (小主机上常开运行即可)
set -e
cd "$(dirname "$(readlink -f "$0")")"

PORT=8088

# 检测局域网 IP（Linux / macOS 通用）
LAN_IP=$( (hostname -I 2>/dev/null | awk '{print $1}') || true )
[ -z "$LAN_IP" ] && LAN_IP=$(ip route get 1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src"){print $(i+1); exit}}')
[ -z "$LAN_IP" ] && LAN_IP=$(ifconfig 2>/dev/null | grep -Eo 'inet (addr:)?([0-9]+\.){3}[0-9]+' | grep -Eo '([0-9]+\.){3}[0-9]+' | grep -v '127.0.0.1' | head -1)

# 重新生成最新源（拉 iptv-org + 测活）
echo "[1/3] 刷新直播源 ..."
python3 make_live_source.py --workers 32 || echo "  (源刷新失败，使用已有 live.txt)"

# 起 http 服务（后台常驻）
echo "[2/3] 启动本地服务 :$PORT ..."
nohup python3 -m http.server "$PORT" --bind 0.0.0.0 >live_http.log 2>&1 &
echo "    PID=$!"

URL="http://${LAN_IP}:${PORT}/live.txt"
echo "[3/3] 完成 ✅"
echo "=============================================="
echo " 把下面这个地址填进 TVBox / OK影视 的『直播源』:"
echo ""
echo "      $URL"
echo ""
echo " 频道数: $(grep -vc '^#' live.txt 2>/dev/null || echo '?')  (已实测可播)"
echo "=============================================="
echo "停止服务: kill \$(cat live_http.log >/dev/null 2>&1; pgrep -f 'http.server $PORT')"

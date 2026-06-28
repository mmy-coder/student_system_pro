#!/bin/bash
# Student Hub 启动脚本 — 一键启动后端 + 内网穿透

cd "$(dirname "$0")"

echo "================================================"
echo "  Student Hub — 启动中..."
echo "================================================"

# 0. 先停掉旧进程
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "cpolar http" 2>/dev/null
sleep 2

# 1. 启动后端
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 --reload > /tmp/uvicorn.log 2>&1 &
BACKEND_PID=$!
sleep 2

# 2. 检查后端
if curl -s http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "[OK] 后端启动成功"
else
    echo "[FAIL] 后端启动失败，查看日志: cat /tmp/uvicorn.log"
    exit 1
fi

# 3. 启动 cpolar
cpolar http 8000 --log=stdout > /tmp/cpolar.log 2>&1 &
CPOLAR_PID=$!
echo "[..] 等待 cpolar 建立隧道..."

# 4. 轮询公网地址
for i in $(seq 1 15); do
    sleep 2
    # 匹配 cpolar 日志中的公网 URL
    PUB_URL=$(grep -oE 'http://[a-z0-9]+\.r[0-9]+\.cpolar\.(top|cn)' /tmp/cpolar.log 2>/dev/null | head -1)
    if [ -n "$PUB_URL" ]; then
        echo ""
        echo "================================================"
        echo "  公网地址: $PUB_URL"
        echo "  本地地址: http://127.0.0.1:8000"
        echo "================================================"
        echo ""
        echo "按 Ctrl+C 停止所有服务"
        break
    fi
done

if [ -z "$PUB_URL" ]; then
    echo "[FAIL] cpolar 隧道建立超时，查看日志: cat /tmp/cpolar.log"
    kill $BACKEND_PID $CPOLAR_PID 2>/dev/null
    exit 1
fi

# 5. 等待 Ctrl+C 退出
trap "echo ''; echo '正在停止...'; kill $BACKEND_PID $CPOLAR_PID 2>/dev/null; echo '已停止，下次直接运行 start.sh 即可'" INT TERM
wait

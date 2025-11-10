#!/bin/bash

# SuperAgent 服务端启动脚本
# 用于启动监控系统服务端

# 设置工作目录
SUPERAGENT_DIR="/opt/superagent"
LOG_DIR="${SUPERAGENT_DIR}/logs"
SERVER_LOG="${LOG_DIR}/server.log"
ERROR_LOG="${LOG_DIR}/error.log"

# 创建日志目录
mkdir -p "${LOG_DIR}"

# 检查Python环境
echo "检查Python环境..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3，请先安装Python3"
    exit 1
fi

# 检查server.py是否存在
if [ ! -f "${SUPERAGENT_DIR}/server/server.py" ]; then
    echo "错误: 找不到server.py文件，请确保路径正确"
    exit 1
fi

# 创建PID文件目录
PID_DIR="${SUPERAGENT_DIR}/pid"
mkdir -p "${PID_DIR}"
PID_FILE="${PID_DIR}/server.pid"

# 检查服务是否已在运行
if [ -f "${PID_FILE}" ]; then
    if ps -p $(cat "${PID_FILE}") > /dev/null; then
        echo "SuperAgent服务已在运行，PID: $(cat "${PID_FILE}")"
        echo "使用以下命令停止服务:"
        echo "  kill $(cat "${PID_FILE}")"
        exit 0
    else
        echo "发现旧的PID文件，但服务未在运行，删除PID文件"
        rm -f "${PID_FILE}"
    fi
fi

# 启动服务
echo "启动SuperAgent服务端..."
echo "日志文件: ${SERVER_LOG}"
echo "错误日志: ${ERROR_LOG}"

# 后台运行服务并记录PID
nohup python3 "${SUPERAGENT_DIR}/server/server.py" > "${SERVER_LOG}" 2> "${ERROR_LOG}" &
SERVER_PID=$!

echo "$SERVER_PID" > "${PID_FILE}"
echo "SuperAgent服务已启动"
echo "服务PID: ${SERVER_PID}"
echo "查看日志: tail -f ${SERVER_LOG}"
echo "停止服务: kill ${SERVER_PID}"

# 检查服务是否成功启动
sleep 2
if ps -p $SERVER_PID > /dev/null; then
    echo "服务启动成功!"
else
    echo "警告: 服务启动失败，请检查错误日志: ${ERROR_LOG}"
    exit 1
fi
#!/bin/bash
# -*- coding: utf-8 -*-

WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxx"


send_alert_to_feishu() {
    local level=$1
    local value=$2
    local hostname=$(hostname)
    local taskname="CPU使用率"
    local time=$(date '+%Y-%m-%d %H:%M:%S')

    local alert_content="${time} 节点 ${hostname} 存在${taskname}异常：当前异常使用值 ${value}"

    local json_payload='{"msg_type":"text","content":{"text":"'"${alert_content}"'"}}'

    curl -s -X POST -H "Content-Type: application/json" -d "${json_payload}" "${WEBHOOK_URL}" > /dev/null
    

    echo "[$(date)] 已发送${level}级别告警: ${alert_content}" >> /var/log/alert.log 2>/dev/null || echo "[$(date)] 已发送${level}级别告警: ${alert_content}"
}

if command -v top &> /dev/null; then

    if [ -f /proc/stat ]; then

        CPU_INFO=$(cat /proc/stat | grep '^cpu ')
        USER=$(echo $CPU_INFO | awk '{print $2}')
        NICE=$(echo $CPU_INFO | awk '{print $3}')
        SYSTEM=$(echo $CPU_INFO | awk '{print $4}')
        IDLE=$(echo $CPU_INFO | awk '{print $5}')
        IOWAIT=$(echo $CPU_INFO | awk '{print $6}')
        IRQ=$(echo $CPU_INFO | awk '{print $7}')
        SOFTIRQ=$(echo $CPU_INFO | awk '{print $8}')

        TOTAL=$((USER + NICE + SYSTEM + IDLE + IOWAIT + IRQ + SOFTIRQ))

        USED=$((TOTAL - IDLE))

        CPU_USAGE=$((USED * 100 / TOTAL))
    else

        CPU_USAGE=$(top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}')

        CPU_USAGE=$(echo "$CPU_USAGE" | awk -F. '{print $1}')
    fi
elif command -v vm_stat &> /dev/null; then

    CPU_USAGE=$(top -l 1 | grep 'CPU usage' | awk '{print $3}' | sed 's/%//g')
else

    CPU_USAGE=0
fi

if [ "$CPU_USAGE" -ge 90 ]; then

    echo "E|${CPU_USAGE}%"

    send_alert_to_feishu "E" "${CPU_USAGE}%"
elif [ "$CPU_USAGE" -ge 70 ]; then

    echo "W|${CPU_USAGE}%"

    send_alert_to_feishu "W" "${CPU_USAGE}%"
elif [ "$CPU_USAGE" -ge 0 ]; then

    echo "I|${CPU_USAGE}%"
else

    echo "O|未知"
fi

exit 0

#!/bin/bash
# -*- coding: utf-8 -*-

WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/xxxxxxxxxxxxxx"


send_alert_to_feishu() {
    local level=$1
    local value=$2
    local hostname=$(hostname)
    local taskname="内存使用率"
    local time=$(date '+%Y-%m-%d %H:%M:%S')
    

    local alert_content="${time} 节点 ${hostname} 存在${taskname}异常：当前异常使用值 ${value} "
    

    local json_payload='{"msg_type":"text","content":{"text":"'"${alert_content}"'"}}'
    

    curl -s -X POST -H "Content-Type: application/json" -d "${json_payload}" "${WEBHOOK_URL}" > /dev/null
    

    echo "[$(date)] 已发送${level}级别告警: ${alert_content}" >> /var/log/alert.log 2>/dev/null || echo "[$(date)] 已发送${level}级别告警: ${alert_content}"
}


if [[ "$(uname)" == "Linux" ]]; then

    MEM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
    MEM_USED=$(free -m | awk '/Mem:/ {print $3}')
    MEM_PERCENT=$(awk "BEGIN {printf \"%.1f\", ${MEM_USED}/${MEM_TOTAL}*100}")
elif [[ "$(uname)" == "Darwin" ]]; then

    MEM_TOTAL=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024)}')  # 转换为MB

    MEM_FREE=$(vm_stat | grep "Pages free:" | awk '{print $3}')
    MEM_ACTIVE=$(vm_stat | grep "Pages active:" | awk '{print $3}')
    MEM_INACTIVE=$(vm_stat | grep "Pages inactive:" | awk '{print $3}')
    MEM_SPECULATIVE=$(vm_stat | grep "Pages speculative:" | awk '{print $3}')
    MEM_WIRED=$(vm_stat | grep "Pages wired down:" | awk '{print $3}')

    PAGE_SIZE=$(sysctl -n hw.pagesize)
    MEM_ACTIVE_MB=$(awk "BEGIN {printf \"%d\", ${MEM_ACTIVE}*${PAGE_SIZE}/1024/1024}")
    MEM_INACTIVE_MB=$(awk "BEGIN {printf \"%d\", ${MEM_INACTIVE}*${PAGE_SIZE}/1024/1024}")
    MEM_SPECULATIVE_MB=$(awk "BEGIN {printf \"%d\", ${MEM_SPECULATIVE}*${PAGE_SIZE}/1024/1024}")
    MEM_WIRED_MB=$(awk "BEGIN {printf \"%d\", ${MEM_WIRED}*${PAGE_SIZE}/1024/1024}")
    
    MEM_USED=$((MEM_ACTIVE_MB + MEM_INACTIVE_MB + MEM_SPECULATIVE_MB + MEM_WIRED_MB))
    MEM_PERCENT=$(awk "BEGIN {printf \"%.1f\", ${MEM_USED}/${MEM_TOTAL}*100}")
else

    MEM_PERCENT="0.0"
    echo "警告: 不支持的操作系统，无法准确检测内存使用情况"
fi


if (( $(echo "$MEM_PERCENT > 70.0" | bc -l) )); then
    LEVEL="W"
    send_alert_to_feishu "W" "${MEM_PERCENT}%"
else
    LEVEL="I"
fi


echo "${LEVEL}|${MEM_PERCENT}%"

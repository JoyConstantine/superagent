#!/bin/bash
# -*- coding: utf-8 -*-

# 定义飞书webhook URL
WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6f9f6771-ef0a-43c1-8d38-59eb59a52968"

# 发送告警到飞书webhook的函数
send_alert_to_feishu() {
    local level=$1
    local value=$2
    local hostname=$(hostname)
    local taskname="内存使用率"
    local time=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 构建告警消息内容
    local alert_content="${time} 节点 ${hostname} 存在${taskname}异常：当前异常使用值 ${value} "
    
    # 构建飞书消息格式 - 使用简单格式避免特殊字符问题
    local json_payload='{"msg_type":"text","content":{"text":"'"${alert_content}"'"}}'
    
    # 使用curl发送POST请求到飞书webhook
    curl -s -X POST -H "Content-Type: application/json" -d "${json_payload}" "${WEBHOOK_URL}" > /dev/null
    
    # 记录日志
    echo "[$(date)] 已发送${level}级别告警: ${alert_content}" >> /var/log/alert.log 2>/dev/null || echo "[$(date)] 已发送${level}级别告警: ${alert_content}"
}

# 检查内存使用情况的脚本
# 输出格式: 级别|值
# 级别定义: 内存使用>70%为W(警告)，<=70%为I(信息)

# 获取内存使用百分比
if [[ "$(uname)" == "Linux" ]]; then
    # Linux系统使用free命令
    MEM_TOTAL=$(free -m | awk '/Mem:/ {print $2}')
    MEM_USED=$(free -m | awk '/Mem:/ {print $3}')
    MEM_PERCENT=$(awk "BEGIN {printf \"%.1f\", ${MEM_USED}/${MEM_TOTAL}*100}")
elif [[ "$(uname)" == "Darwin" ]]; then
    # macOS系统使用vm_stat命令
    MEM_TOTAL=$(sysctl -n hw.memsize | awk '{print int($1/1024/1024)}')  # 转换为MB
    # 使用vm_stat计算已用内存
    MEM_FREE=$(vm_stat | grep "Pages free:" | awk '{print $3}')
    MEM_ACTIVE=$(vm_stat | grep "Pages active:" | awk '{print $3}')
    MEM_INACTIVE=$(vm_stat | grep "Pages inactive:" | awk '{print $3}')
    MEM_SPECULATIVE=$(vm_stat | grep "Pages speculative:" | awk '{print $3}')
    MEM_WIRED=$(vm_stat | grep "Pages wired down:" | awk '{print $3}')
    
    # 计算已用内存 (单位: MB)
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


# 确定告警级别
if (( $(echo "$MEM_PERCENT > 70.0" | bc -l) )); then
    LEVEL="W"
    send_alert_to_feishu "W" "${MEM_PERCENT}%"
else
    LEVEL="I"
fi


echo "${LEVEL}|${MEM_PERCENT}%"
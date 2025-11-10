#!/bin/bash
# -*- coding: utf-8 -*-

# 定义飞书webhook URL
WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6f9f6771-ef0a-43c1-8d38-59eb59a52968"

# 发送告警到飞书webhook的函数
send_alert_to_feishu() {
    local level=$1
    local value=$2
    local hostname=$(hostname)
    local taskname="CPU使用率"
    local time=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 构建告警消息内容
    local alert_content="${time} 节点 ${hostname} 存在${taskname}异常：当前异常使用值 ${value}"
    
    # 构建飞书消息格式 - 使用更简单的格式避免特殊字符问题
    local json_payload='{"msg_type":"text","content":{"text":"'"${alert_content}"'"}}'
    
    # 使用curl发送POST请求到飞书webhook
    curl -s -X POST -H "Content-Type: application/json" -d "${json_payload}" "${WEBHOOK_URL}" > /dev/null
    
    # 记录日志
    echo "[$(date)] 已发送${level}级别告警: ${alert_content}" >> /var/log/alert.log 2>/dev/null || echo "[$(date)] 已发送${level}级别告警: ${alert_content}"
}


# 获取CPU使用率
if command -v top &> /dev/null; then
    # Linux系统
    if [ -f /proc/stat ]; then
        # 读取CPU使用情况
        CPU_INFO=$(cat /proc/stat | grep '^cpu ')
        USER=$(echo $CPU_INFO | awk '{print $2}')
        NICE=$(echo $CPU_INFO | awk '{print $3}')
        SYSTEM=$(echo $CPU_INFO | awk '{print $4}')
        IDLE=$(echo $CPU_INFO | awk '{print $5}')
        IOWAIT=$(echo $CPU_INFO | awk '{print $6}')
        IRQ=$(echo $CPU_INFO | awk '{print $7}')
        SOFTIRQ=$(echo $CPU_INFO | awk '{print $8}')
        
        # 计算总的CPU时间
        TOTAL=$((USER + NICE + SYSTEM + IDLE + IOWAIT + IRQ + SOFTIRQ))
        # 计算使用的CPU时间
        USED=$((TOTAL - IDLE))
        # 计算CPU使用率
        CPU_USAGE=$((USED * 100 / TOTAL))
    else
        # 备用方法
        CPU_USAGE=$(top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}')
        # 转换为整数
        CPU_USAGE=$(echo "$CPU_USAGE" | awk -F. '{print $1}')
    fi
elif command -v vm_stat &> /dev/null; then
    # macOS系统
    # 这里使用简化的方法，实际应该使用更复杂的计算
    CPU_USAGE=$(top -l 1 | grep 'CPU usage' | awk '{print $3}' | sed 's/%//g')
else
    # 其他系统
    CPU_USAGE=0
fi

# 根据CPU使用率确定输出级别
if [ "$CPU_USAGE" -ge 90 ]; then
    # CPU使用率超过90%，错误级别
    echo "E|${CPU_USAGE}%"
    # 发送告警到飞书
    send_alert_to_feishu "E" "${CPU_USAGE}%"
elif [ "$CPU_USAGE" -ge 70 ]; then
    # CPU使用率超过70%，警告级别
    echo "W|${CPU_USAGE}%"
    # 发送告警到飞书
    send_alert_to_feishu "W" "${CPU_USAGE}%"
elif [ "$CPU_USAGE" -ge 0 ]; then
    # 正常级别
    echo "I|${CPU_USAGE}%"
else
    # 其他情况
    echo "O|未知"
fi

exit 0
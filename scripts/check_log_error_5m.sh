#!/bin/bash
# -*- coding: utf-8 -*-

# 定义飞书webhook URL
WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/6f9f6771-ef0a-43c1-8d38-59eb59a52968"

# 日志文件路径
LOG_FILE="/opt/pcdnd/logs/pcdnd.log"

# 发送告警到飞书webhook的函数
send_alert_to_feishu() {
    local alert_content=$1
    local time=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 构建飞书消息格式
    local json_payload='{"msg_type":"text","content":{"text":"'"${alert_content}"'"}}'
    
    # 使用curl发送POST请求到飞书webhook
    curl -s -X POST -H "Content-Type: application/json" -d "${json_payload}" "${WEBHOOK_URL}" > /dev/null
    
    # 记录日志
    echo "[$time] 已发送告警: ${alert_content}" >> /var/log/alert.log 2>/dev/null || echo "[$time] 已发送告警: ${alert_content}"
}

# 检查日志文件是否存在
if [ ! -f "$LOG_FILE" ]; then
    echo "I|日志文件不存在: $LOG_FILE"
    exit 0
fi

# 获取当前时间和前一分钟的时间戳
CURRENT_TIME=$(date +%s)
ONE_MINUTE_AGO=$((CURRENT_TIME - 60))

# 收集错误日志
ERROR_LOGS=$(mktemp)

# 高效过滤方法：使用grep和awk直接过滤前一分钟且status不等于2xx的记录
# 获取前一分钟的时间范围（格式：2025-11-10T13:43:50）
ONE_MINUTE_AGO_STR=$(date -d "1 minute ago" '+%Y-%m-%dT%H:%M:%S')

# 使用grep过滤时间范围内的日志，然后再过滤status不等于2xx的记录
cat "$LOG_FILE" | grep -E "^$ONE_MINUTE_AGO_STR|^$(date -d "1 minute ago" '+%Y-%m-%dT%H:%M')" | \
grep -v 'status=2[0-9][0-9]' | grep 'status=[0-9]\+' > "$ERROR_LOGS"

# 为了确保不遗漏，再用另一种方式补充过滤
if [ ! -s "$ERROR_LOGS" ]; then
    # 如果上面的过滤没有结果，使用更宽松的时间过滤
    ONE_MINUTE_AGO_DATE=$(date -d "1 minute ago" '+%Y-%m-%d')
    cat "$LOG_FILE" | grep "^$ONE_MINUTE_AGO_DATE" | \
    grep -v 'status=2[0-9][0-9]' | grep 'status=[0-9]\+' > "$ERROR_LOGS"
fi

# 统计错误数量
ERROR_COUNT=$(wc -l < "$ERROR_LOGS")

# 如果错误数量超过10，则进行告警
if [[ $ERROR_COUNT -gt 10 ]]; then
    # 统计不同status的错误数量
    STATUS_COUNTS=$(grep -o 'status=[0-9]\+' "$ERROR_LOGS" | sort | uniq -c | sort -nr)
    
    # 统计相同fid的servecode信息
    FID_SERVCODES=$(grep -o 'fid="[^"\"]*" servecode=[0-9]\+' "$ERROR_LOGS" | sort | uniq -c | sort -nr)
    
    # 获取主机名
    HOSTNAME=$(hostname)
    # 获取当前告警时间
    ALERT_TIME=$(date '+%Y-%m-%d %H:%M:%S')
    
    # 构建告警信息
    ALERT_CONTENT="${ALERT_TIME} ${HOSTNAME}\n"
    ALERT_CONTENT+="错误总数量: ${ERROR_COUNT}\n"
    ALERT_CONTENT+="各错误状态码统计:\n"
    
    # 添加各status的统计信息
    echo "$STATUS_COUNTS" | while read -r count status; do
        status_code=$(echo "$status" | cut -d'=' -f2)
        ALERT_CONTENT+="status ${status_code} 错误数量${count}\n"
    done
    
    # 添加相同fid的servecode信息
    if [[ ! -z "$FID_SERVCODES" ]]; then
        ALERT_CONTENT+="\n相同FID的servecode信息:\n"
        echo "$FID_SERVCODES" | while read -r count fid_servecode; do
            fid=$(echo "$fid_servecode" | grep -o 'fid="[^"\"]*"' | cut -d'"' -f2)
            servecode=$(echo "$fid_servecode" | grep -o 'servecode=[0-9]\+' | cut -d'=' -f2)
            ALERT_CONTENT+="FID: ${fid} 出现 ${count} 次, servecode ${servecode}\n"
        done
    fi
    
    # 发送告警到飞书
    send_alert_to_feishu "${ALERT_CONTENT}"
    
    # 输出告警级别和错误数量
    echo "W|错误数量: ${ERROR_COUNT}"
else
    # 错误数量不超过阈值，输出正常级别
    echo "I|错误数量: ${ERROR_COUNT}"
fi

# 清理临时文件
rm -f "$ERROR_LOGS"

exit 0
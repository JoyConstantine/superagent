#!/bin/bash

FEISHU_WEBHOOK_URL="https://open.feishu.cn/open-apis/bot/v2/hook/12345678-1234-1234-1234-123456789012"

ROOT_WARNING_THRESHOLD=85
OTHER_WARNING_THRESHOLD=95

current_time=$(date '+%Y-%m-%d %H:%M:%S')

hostname=$(hostname)

send_alert_to_feishu() {
    local alert_level=$1
    local message=$2
    
    alert_content="${current_time} ${hostname} ${message}"
    
    json_payload="{\"msg_type\":\"text\",\"content\":{\"text\":\"${alert_content}\"}}"
    
    curl -s -X POST -H "Content-Type: application/json" -d "$json_payload" "$FEISHU_WEBHOOK_URL" > /dev/null
}

check_disk_usage() {
    if ! command -v df &> /dev/null; then
        echo "E| 未找到df命令，无法检查磁盘使用情况"
        send_alert_to_feishu "E" "未找到df命令，无法检查磁盘使用情况"
        return 1
    fi
    
    disk_info=$(df -h | grep -vE 'Filesystem|tmpfs|cdrom|udev')
    
    echo "$disk_info" | while read -r line; do
        mount_point=$(echo "$line" | awk '{print $6}')
        usage=$(echo "$line" | awk '{print $5}' | sed 's/%//g')
        total_space=$(echo "$line" | awk '{print $2}')
        available_space=$(echo "$line" | awk '{print $4}')
        
        if [ -z "$mount_point" ] || [ -z "$usage" ]; then
            continue
        fi
        
        if [ "$mount_point" = "/" ]; then
            if [ "$usage" -ge "$ROOT_WARNING_THRESHOLD" ]; then
                echo "W| 磁盘 $mount_point 使用率 ${usage}% 超过阈值 ${ROOT_WARNING_THRESHOLD}% 总空间 ${total_space} 可用 ${available_space}"
                send_alert_to_feishu "W" "磁盘 $mount_point 使用率 ${usage}% 超过阈值 ${ROOT_WARNING_THRESHOLD}% 总空间 ${total_space} 可用 ${available_space}"
            fi
        else
            if [ "$usage" -ge "$OTHER_WARNING_THRESHOLD" ]; then
                echo "W| 磁盘 $mount_point 使用率 ${usage}% 超过阈值 ${OTHER_WARNING_THRESHOLD}% 总空间 ${total_space} 可用 ${available_space}"
                send_alert_to_feishu "W" "磁盘 $mount_point 使用率 ${usage}% 超过阈值 ${OTHER_WARNING_THRESHOLD}% 总空间 ${total_space} 可用 ${available_space}"
            fi
        fi
    done
}

main() {
    if ! command -v curl &> /dev/null; then
        echo "E| 未找到curl命令，无法发送告警到飞书"
        exit 1
    fi
    
    check_disk_usage
}

main
#!/bin/bash
# -*- coding: utf-8 -*-


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
elif [ "$CPU_USAGE" -ge 70 ]; then
    # CPU使用率超过70%，警告级别
    echo "W|${CPU_USAGE}%"
elif [ "$CPU_USAGE" -ge 0 ]; then
    # 正常级别
    echo "I|${CPU_USAGE}%"
else
    # 其他情况
    echo "O|未知"
fi

exit 0
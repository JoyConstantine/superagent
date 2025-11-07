#!/bin/bash
# -*- coding: utf-8 -*-
"""
SuperAgent 环境设置脚本
用于在 Linux/Mac 系统上设置运行环境
"""

set -e

echo "===== SuperAgent 环境设置 ===="

# 检查 Python 版本
echo "检查 Python 版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 6 ]; then
    echo "错误: 需要 Python 3.6 或更高版本，当前版本为 $PYTHON_VERSION"
    exit 1
fi
echo "Python 版本检查通过: $PYTHON_VERSION"

# 创建必要的目录
echo "创建必要的目录..."
mkdir -p server/data agent/logs client/logs

# 创建脚本存储目录（在实际部署时需要在节点上创建）
echo "提示: 在节点服务器上需要创建脚本目录 /opt/script/superagent/"

# 设置脚本可执行权限
echo "设置脚本可执行权限..."
chmod +x scripts/*.sh 2>&1 || true

# 创建 super 快捷命令
echo "创建 super 快捷命令..."
SUPERAGENT_DIR=$(pwd)

cat > /tmp/super_alias.sh << 'EOF'
# SuperAgent 快捷命令别名
function super() {
    python3 "$SUPERAGENT_DIR/client/client.py" 192.168.123.178:4567 --user=admin --passwd="rL1|aB2#oE2!kR4~aC2<" "$@"
}

# 将别名添加到 shell 配置文件
echo "super 函数已定义，可以使用以下命令调用:"
echo "super -l       # 列出所有任务"
echo "super -t taskname -I  # 查询 INFO 级别结果"
echo "super -a script.sh  # 下发任务"
echo "super -d taskname  # 删除任务"
echo "super -c taskname  # 清除任务记录"
echo "super -s taskname  # 查看脚本内容"
EOF

# 尝试将别名添加到各种 shell 配置文件
for profile in ~/.bashrc ~/.zshrc ~/.bash_profile ~/.profile; do
    if [ -f "$profile" ]; then
        echo "将 super 快捷命令添加到 $profile"
        sed -i '/^function super()/d; /^}/d; /^# SuperAgent/d' "$profile"
        sed -i "s/SUPERAGENT_DIR=.*/SUPERAGENT_DIR=$SUPERAGENT_DIR/" /tmp/super_alias.sh
        cat /tmp/super_alias.sh >> "$profile"
        echo "请运行 'source $profile' 使别名立即生效"
        break
    fi
done

# 显示使用说明
echo -e "\n===== SuperAgent 使用说明 ====="
echo "1. 启动服务端:"
echo "   cd server && python3 server.py"
echo ""
echo "2. 启动节点代理（在每个被监控节点上）:"
echo "   cd agent && python3 agent.py"
echo ""
echo "3. 使用客户端命令（通过 super 快捷命令）:"
echo "   super -l       # 列出所有任务"
echo "   super -t taskname -I  # 查询 INFO 级别结果"
echo "   super -a script.sh  # 下发任务"
echo "   super -d taskname  # 删除任务"
echo "   super -c taskname  # 清除任务记录"
echo "   super -s taskname  # 查看脚本内容"
echo ""
echo "4. 查看日志:"
echo "   server/superagent_server.log"
echo "   agent/superagent_agent.log"
echo "   client/superagent_client.log"
echo ""
echo "===== 设置完成 ====="
echo "请确保服务端、节点代理和客户端之间的网络连接正常"
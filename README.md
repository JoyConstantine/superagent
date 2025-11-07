# SuperAgent 分布式监控系统

SuperAgent 是一个轻量级的分布式监控系统，由服务端、节点代理和客户端三部分组成，用于集中管理和监控分布式节点。

## 系统架构

- **服务端 (Server)**: 运行在中央服务器上，负责接收节点上报数据、管理任务、处理客户端指令
- **节点代理 (Agent)**: 运行在被监控的节点上，执行服务端下发的脚本并上报结果
- **客户端 (Client)**: 用于向服务端发送指令，查询监控数据

## 功能特点

1. **集中管理**: 通过服务端统一管理所有监控节点
2. **任务分发**: 自动将监控脚本分发到所有节点
3. **周期性执行**: 根据脚本名称自动识别执行周期（如5m表示每5分钟执行）
4. **结果分级**: 支持INFO(I)、WARNING(W)、ERROR(E)和OTHER(O)四个级别的日志输出
5. **认证安全**: 客户端需要用户名密码认证才能访问服务端
6. **数据持久化**: 监控结果自动保存到文件系统
7. **心跳机制**: 节点定期向服务端发送心跳，确保连接正常

## 快速开始

### 安装依赖

系统主要使用Python标准库，无需额外安装依赖包。

### 运行服务端

在服务器上执行：

```bash
cd server
python server.py
```

服务端默认监听地址：
- 客户端连接：0.0.0.0:4567
- 节点连接：0.0.0.0:4568

### 运行节点代理

在需要监控的节点上执行：

```bash
cd agent
python agent.py
```

默认连接到 192.168.1.1:4568，请根据实际情况修改 SERVER_HOST 配置。

### 使用客户端

```bash
cd client
python client.py --help
```

## 命令使用

### 1. 查询任务结果

```bash
# 基本查询
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -t check_kuaishou_cpu

# 查询INFO级别的结果
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -t check_kuaishou_cpu -I
```

### 2. 列出所有任务

```bash
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -l
```

### 3. 删除任务

```bash
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -d check_kuaishou_cpu
```

### 4. 下发任务

```bash
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -a check_kuaishou_cpu_5m.sh
```

### 5. 清除任务记录

```bash
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -c check_kuaishou_cpu
```

### 6. 显示脚本内容

```bash
python client.py 192.168.1.1:4567 --user=admin --passwd=rL1|aB2#oE2!kR4~aC2< -s check_kuaishou_cpu
```

## 脚本规范

### 脚本命名规范

脚本名称必须遵循以下格式：

```
taskname_interval.sh
```

其中：
- `taskname`: 任务名称（自定义）
- `interval`: 执行周期，格式为 `数字+单位`
  - `s`: 秒（如 30s）
  - `m`: 分钟（如 5m）
  - `h`: 小时（如 1h）
  - `d`: 天（如 1d）

例如：
- `check_kuaishou_cpu_5m.sh` - 每5分钟检查一次CPU
- `check_disk_usage_1h.sh` - 每小时检查一次磁盘使用情况

### 脚本输出规范

脚本必须按照以下格式输出结果：

```
级别|值
```

支持的级别：
- `I`: INFO 级别
- `W`: WARNING 级别
- `E`: ERROR 级别
- 未按格式输出或其他情况默认为 `O` 级别

例如：
```
I|56%
W|85%
E|95%
```

## 环境变量和配置

### 服务端配置

在 `server.py` 中可以修改以下配置：
- `SERVER_HOST`: 监听地址（默认：0.0.0.0）
- `SERVER_PORT`: 客户端连接端口（默认：4567）
- `NODE_PORT`: 节点连接端口（默认：4568）
- `SCRIPT_DIR`: 节点上脚本存放目录（默认：/opt/script/superagent/）
- `DATA_DIR`: 数据保存目录（默认：./data）
- `USERS`: 用户认证信息（可在代码中修改）

### 节点代理配置

在 `agent.py` 中可以修改以下配置：
- `SERVER_HOST`: 服务端地址（默认：192.168.1.1）
- `SERVER_PORT`: 服务端节点连接端口（默认：4568）
- `SCRIPT_DIR`: 脚本存放目录（默认：/opt/script/superagent/）

### 客户端配置

客户端支持通过命令行参数配置：
- 服务端地址和端口（位置参数）
- 用户名（--user）
- 密码（--passwd）

## 日志

所有组件都会生成日志文件：
- `superagent_server.log`: 服务端日志
- `superagent_agent.log`: 节点代理日志
- `superagent_client.log`: 客户端日志

## 示例脚本

项目提供了一个示例脚本 `check_kuaishou_cpu_5m.sh`，用于每5分钟检查一次CPU使用情况。

- CPU使用率 < 70%: 输出 INFO 级别（I）
- 70% <= CPU使用率 < 90%: 输出 WARNING 级别（W）
- CPU使用率 >= 90%: 输出 ERROR 级别（E）

## 注意事项

1. 确保服务端、节点代理和客户端之间的网络连接正常
2. 节点代理需要有足够的权限在 /opt/script/superagent/ 目录下创建和执行脚本
3. 脚本必须具有可执行权限（节点代理会自动添加）
4. 脚本执行超时时间为5分钟
5. 建议在Linux/Mac系统上运行，Windows系统可能需要调整部分脚本命令

## 常见问题

### 节点连接不上服务端？
- 检查服务端是否正在运行
- 检查网络连接和防火墙设置
- 确认服务端地址和端口配置正确

### 任务下发失败？
- 检查脚本名称是否符合规范
- 确认脚本文件存在于服务端的 scripts 目录中
- 查看服务端日志获取详细错误信息

### 脚本执行失败？
- 检查脚本内容是否正确
- 确认节点有足够的权限执行脚本
- 查看节点代理日志获取详细错误信息

## 扩展和定制

### 添加新用户
在服务端的 `USERS` 字典中添加新的用户名和密码。

### 创建自定义监控脚本
1. 在 `scripts` 目录下创建新脚本
2. 遵循脚本命名规范和输出格式
3. 使用客户端下发任务

### 修改数据存储方式
当前系统使用文件系统存储数据，可以根据需要修改为数据库存储。
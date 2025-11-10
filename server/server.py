#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控系统服务端
负责管理节点连接、处理客户端指令、存储任务结果
"""

import socket
import json
import os
import time
import asyncio
import logging
import hashlib
import re
import threading
from datetime import datetime
from collections import defaultdict
from typing import Dict, List, Optional, Any

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='superagent_server.log'
)
logger = logging.getLogger('superagent-server')

# 配置客户端操作日志
client_logger = logging.getLogger('client-operations')
client_logger.setLevel(logging.INFO)
# 创建文件处理器，写入client.log
client_handler = logging.FileHandler('client.log')
client_handler.setFormatter(logging.Formatter('%(asctime)s - %(username)s - %(command)s - %(success)s - %(client_ip)s:%(client_port)s'))
client_logger.addHandler(client_handler)

# 全局配置
SERVER_HOST = '0.0.0.0'
SERVER_PORT = 4567
NODE_PORT = 4568  # 节点连接端口
SCRIPT_DIR = '/opt/script/superagent/'
DATA_DIR = './data'
HEARTBEAT_TIMEOUT = 60  # 心跳超时时间（秒）

# 用户认证信息
# 格式: {用户名: 密码}
USERS = {
    'admin': 'rL1|aB2#oE2!kR4~aC2<',  # 管理员用户
    'operator': 'oP3$eR4@t0r5!',     # 操作员用户
    'viewer': 'vI3#wE2$eR1@'         # 查看员用户
}

# 用于节点验证的密钥
NODE_SECRET_KEY = 'superagent_secret_key_2024'  # 生产环境中应该使用更强的密钥并通过环境变量或配置文件管理

# 存储已连接的节点信息
connected_nodes = {}

# 存储任务信息
class Task:
    def __init__(self, task_name, script_content, interval):
        self.task_name = task_name
        self.script_content = script_content
        self.interval = interval  # 执行间隔（秒）
        self.created_at = datetime.now().isoformat()
        self.results = {}
        self._modified = False  # 标记是否被修改，用于延迟保存
    
    def update_result(self, node_id, result_data):
        """更新任务结果，并标记为已修改"""
        self.results[node_id] = result_data
        self._modified = True
    
    def mark_saved(self):
        """标记任务结果已保存"""
        self._modified = False

# 所有任务
all_tasks = {}

# 创建数据目录
os.makedirs(DATA_DIR, exist_ok=True)

class NodeConnection:
    """管理与单个节点的连接"""
    def __init__(self, reader, writer, client_address):
        self.reader = reader
        self.writer = writer
        self.address = client_address
        self.node_id = None  # 服务端生成的唯一标识ID
        self.hostname = None  # 节点的主机名
        self.last_heartbeat = time.time()
        self.status = 'online'
        
    async def send_message(self, message):
        """向节点发送消息"""
        try:
            data = (json.dumps(message) + '\n').encode('utf-8')
            self.writer.write(data)
            await self.writer.drain()
            logger.debug(f"向节点 {self.node_id} 发送消息: {message}")
        except Exception as e:
            logger.error(f"向节点 {self.node_id} 发送消息失败: {e}")
            await self.close()
    
    async def close(self):
        """关闭连接"""
        try:
            self.writer.close()
            await self.writer.wait_closed()
            self.status = 'offline'
            if self.node_id and self.node_id in connected_nodes:
                del connected_nodes[self.node_id]
            logger.info(f"节点 {self.node_id} 连接已关闭")
        except Exception as e:
            logger.error(f"关闭节点 {self.node_id} 连接失败: {e}")

# 使用锁保护共享资源
connected_nodes_lock = asyncio.Lock()
tasks_lock = asyncio.Lock()

# 批量保存结果配置
BATCH_SAVE_INTERVAL = 5  # 批量保存间隔（秒）
pending_saves = set()  # 待保存的任务集合
last_batch_save_time = time.time()

# 性能优化配置
MAX_CACHE_SIZE = 1000  # 最大缓存条目数
NODE_TIMEOUT = 60  # 节点超时时间（秒）

def authenticate_user(username, password):
    """验证用户身份"""
    if username in USERS and USERS[username] == password:
        return True
    return False

def generate_node_id(address, hostname):
    """生成节点ID（基于地址和主机名，更加稳定）"""
    # 使用IP地址和主机名生成更稳定的ID，减少重复生成可能
    unique_str = f"{address[0]}:{address[1]}:{hostname}"
    # 使用hashlib.sha1替代md5以获得更好的唯一性
    return hashlib.sha1(unique_str.encode()).hexdigest()[:12]

def parse_interval(script_name):
    """从脚本名称解析执行间隔（秒）"""
    match = re.search(r'_(\d+[smhd])\.sh$', script_name)
    if not match:
        return None
    
    time_str = match.group(1)
    value = int(time_str[:-1])
    unit = time_str[-1]
    
    if unit == 's':
        return value
    elif unit == 'm':
        return value * 60
    elif unit == 'h':
        return value * 3600
    elif unit == 'd':
        return value * 86400
    
    return None

def validate_script_name(script_name):
    """验证脚本名称是否符合规范"""
    if not script_name.endswith('.sh'):
        return False, "脚本必须以.sh结尾"
    
    parts = script_name[:-3].split('_')
    if len(parts) < 2:
        return False, "脚本名称格式不正确，应为name_timeunit"
    
    timeunit = parts[-1]
    if timeunit[-1] not in ['s', 'm', 'h', 'd']:
        return False, "时间单位必须为s(秒)、m(分钟)、h(小时)或d(天)"
    
    try:
        time_value = timeunit[:-1]
        if not time_value.isdigit():
            return False, "时间值必须为数字"
        int(time_value)
    except ValueError:
        return False, "时间值格式不正确"
    
    return True, ""

async def handle_node(reader, writer):
    """处理节点连接（异步版本）"""
    client_address = writer.get_extra_info('peername')
    node = NodeConnection(reader, writer, client_address)
    node.node_id = None  # 将在验证成功后设置
    
    logger.info(f"新的节点连接尝试: {client_address[0]}:{client_address[1]}")
    
    try:
        # 等待节点发送认证信息
        data = await reader.read(4096)
        if not data:
            await send_auth_response(writer, False, "连接已关闭")
            return
        
        auth_message = json.loads(data.decode('utf-8'))
        
        # 验证节点密钥
        if auth_message.get('type') != 'auth' or auth_message.get('secret_key') != NODE_SECRET_KEY:
            await send_auth_response(writer, False, "无效的节点密钥")
            logger.warning(f"节点 {client_address} 认证失败: 无效密钥")
            return
        
        # 获取节点主机名
        node.hostname = auth_message.get('hostname', 'unknown')
        
        # 认证成功，生成节点ID（基于地址和主机名）
        node.node_id = generate_node_id(client_address, node.hostname)
        
        # 使用锁保护connected_nodes字典
        async with connected_nodes_lock:
            # 检查是否已存在相同主机名的节点，如果存在则替换
            for existing_node_id, existing_node in list(connected_nodes.items()):
                if existing_node.hostname == node.hostname and existing_node_id != node.node_id:
                    logger.info(f"检测到主机名 {node.hostname} 的节点已存在，替换旧节点连接")
                    try:
                        await existing_node.close()
                    except Exception as e:
                        logger.error(f"关闭旧节点连接失败: {e}")
            
            # 添加新节点
            connected_nodes[node.node_id] = node
        
        logger.info(f"节点 {node.node_id} ({node.hostname} @ {client_address[0]}:{client_address[1]}) 认证成功")
        
        # 发送认证成功响应和握手消息
        await send_auth_response(writer, True, "认证成功")
        
        # 发送握手消息，包含节点ID和主机名信息
        handshake_msg = {
            'type': 'handshake',
            'node_id': node.node_id,
            'hostname': node.hostname
        }
        await node.send_message(handshake_msg)
        logger.debug(f"已向节点 {node.node_id}({node.hostname}) 发送握手消息")
        
        # 发送所有已存在的任务
        async with tasks_lock:
            tasks_list = list(all_tasks.keys())
            task_dict = all_tasks.copy()
        
        for task_name in tasks_list:
            task = task_dict[task_name]
            task_msg = {
                'type': 'task',
                'task_name': task_name,
                'script_content': task.script_content,
                'interval': task.interval
            }
            await node.send_message(task_msg)
        
        # 发送任务同步消息
        sync_msg = {
            'type': 'tasks_sync',
            'tasks': tasks_list
        }
        await node.send_message(sync_msg)
        
        # 处理消息循环
        buffer = ''
        while True:
            # 异步读取数据
            data = await reader.read(4096)
            if not data:
                break
            
            # 处理可能的多条消息
            buffer += data.decode('utf-8')
            while '\n' in buffer:
                line, buffer = buffer.split('\n', 1)
                if not line.strip():
                    continue
                
                try:
                    message = json.loads(line)
                    node.last_heartbeat = time.time()
                    
                    if message['type'] == 'heartbeat':
                        # 响应心跳，包含节点标识信息
                        await node.send_message({
                            'type': 'heartbeat_response',
                            'node_id': node.node_id,
                            'hostname': node.hostname
                        })
                    elif message['type'] == 'task_result':
                        # 处理任务执行结果
                        # 确保结果中包含正确的节点信息
                        if 'hostname' not in message:
                            message['hostname'] = node.hostname
                        await process_task_result(node, message)
                except json.JSONDecodeError as e:
                    logger.error(f"解析节点 {node.node_id} 消息失败: {e}")
    
    except json.JSONDecodeError:
        logger.warning(f"节点 {client_address} 发送的验证信息格式错误")
        await send_auth_response(writer, False, "无效的请求格式")
    except Exception as e:
        logger.error(f"处理节点 {node.node_id or client_address} 连接时出错: {e}")
    finally:
        await node.close()

async def send_auth_response(writer, success, message):
    """发送认证响应"""
    response = {
        'type': 'auth_response',
        'success': success,
        'message': message
    }
    try:
        writer.write((json.dumps(response) + '\n').encode('utf-8'))
        await writer.drain()
    except Exception as e:
        logger.error(f"发送认证响应失败: {e}")
    finally:
        if not success and not writer.is_closing():
            writer.close()
            await writer.wait_closed()

async def process_task_result(node, message):
    """处理任务执行结果（异步版本）"""
    task_name = message.get('task_name')
    timestamp = message.get('timestamp', datetime.now().isoformat())
    level = message.get('level', 'O')
    value = message.get('value', '')
    
    # 优先使用message中的hostname，如果没有则使用node的hostname，最后才使用node_id
    hostname = message.get('hostname', node.hostname)
    
    result_data = {
        'timestamp': timestamp,
        'level': level,
        'value': value,
        'hostname': hostname,
        'node_id': node.node_id  # 同时保存node_id以便后续查询
    }
    
    # 保存结果
    async with tasks_lock:
        if task_name in all_tasks:
            all_tasks[task_name].update_result(node.node_id, result_data)
            # 添加到待保存集合
            pending_saves.add(task_name)
    
    # 检查是否需要批量保存
    global last_batch_save_time
    current_time = time.time()
    if current_time - last_batch_save_time >= BATCH_SAVE_INTERVAL:
        asyncio.create_task(batch_save_results())
        last_batch_save_time = current_time
    
    logger.info(f"收到节点 {node.node_id}({node.hostname}) 任务 {task_name} 执行结果: {level} {value}")

async def batch_save_results():
    """批量保存任务结果"""
    if not pending_saves:
        return
    
    # 复制待保存的任务集合，然后清空原集合
    tasks_to_save = set(pending_saves)
    pending_saves.clear()
    
    # 批量保存
    for task_name in tasks_to_save:
        # 只保存被修改的任务
        async with tasks_lock:
            if task_name in all_tasks and all_tasks[task_name]._modified:
                # 异步执行保存（实际仍为同步I/O，但通过asyncio.create_task并发执行）
                asyncio.create_task(save_task_results_async(task_name))
                # 标记为已保存
                all_tasks[task_name].mark_saved()

def save_task_results(task_name):
    """保存任务结果到文件（同步版本，保留向后兼容）"""
    if task_name not in all_tasks:
        return
    
    file_path = os.path.join(DATA_DIR, f"task_{task_name}.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                'task_name': task_name,
                'created_at': all_tasks[task_name].created_at,
                'interval': all_tasks[task_name].interval,
                'results': all_tasks[task_name].results
            }, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存任务 {task_name} 结果失败: {e}")

async def save_task_results_async(task_name):
    """异步保存任务结果（通过线程池执行I/O操作）"""
    # 使用线程池执行同步I/O操作，避免阻塞事件循环
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, save_task_results, task_name)

def load_task_results():
    """从文件加载任务结果"""
    global all_tasks
    
    for filename in os.listdir(DATA_DIR):
        if filename.startswith('task_') and filename.endswith('.json'):
            try:
                file_path = os.path.join(DATA_DIR, filename)
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    task_name = data['task_name']
                    # 只恢复结果，不恢复脚本内容
                    if task_name not in all_tasks:
                        # 如果任务不存在，创建一个空任务
                        all_tasks[task_name] = Task(task_name, '', data['interval'])
                    all_tasks[task_name].results = data['results']
                    all_tasks[task_name].created_at = data['created_at']
            except Exception as e:
                logger.error(f"加载任务结果文件 {filename} 失败: {e}")

async def async_send_to_nodes(message):
    """异步向所有节点发送消息"""
    executed_count = 0
    failed_count = 0
    
    # 创建所有发送任务
    send_tasks = []
    async with connected_nodes_lock:
        # 创建一个副本以避免在迭代过程中修改
        nodes_copy = list(connected_nodes.items())
        for node_id, node in nodes_copy:
            send_tasks.append((node_id, node.hostname, node.send_message(message)))
    
    # 并行等待所有发送任务完成
    for node_id, hostname, send_task in send_tasks:
        try:
            await send_task
            executed_count += 1
        except Exception as e:
            logger.error(f"向节点 {node_id}({hostname}) 发送消息失败: {e}")
            failed_count += 1
    
    return executed_count, failed_count

def handle_client_command(command, username, script_name=None, script_content=None):
    """处理客户端命令"""
    parts = command.split()
    if len(parts) < 1:
        return {"success": False, "message": "命令格式错误"}
    
    # 检查用户权限
    # 这里可以根据需要扩展不同用户的权限控制
    if username == 'viewer':
        # 查看员只能执行查询类命令
        if parts[0] not in ['-t', '-l']:
            return {"success": False, "message": "权限不足，查看员只能执行查询类命令"}
    
    cmd = parts[0]
    
    if cmd == '-t':  # 查询任务结果
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        level = None
        if len(parts) > 2:
            # 支持两种格式：带'-'前缀的('-I', '-O', '-W', '-E')和直接字符('I', 'O', 'W', 'E')
            if parts[2] in ['-I', '-O', '-W', '-E']:
                level = parts[2][1]  # 提取级别字符（去掉-）
            elif parts[2] in ['I', 'O', 'W', 'E']:
                level = parts[2]  # 直接使用级别字符
        
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 构建结果响应
        results = []
        for node_id, result in all_tasks[task_name].results.items():
            # 根据级别过滤
            if level and result.get('level', 'O') != level:
                continue
            
            # 格式化时间
            try:
                timestamp = datetime.fromisoformat(result['timestamp'])
                time_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = result['timestamp']
            
            # 优先使用hostname，如果没有则使用node_id
            display_name = result.get('hostname', node_id)
            results.append(f"{time_str} {result['level']} {display_name} {result['value']}")
        
        return {"success": True, "data": results}
    
    elif cmd == '-l':  # 列出所有任务
        if not all_tasks:
            return {"success": True, "message": "当前没有任务"}
        
        return {"success": True, "data": list(all_tasks.keys())}
    
    elif cmd == '-n':  # 立即执行任务
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 同步环境中创建异步任务并等待其完成
        execute_msg = {
            'type': 'execute_task',
            'task_name': task_name
        }
        
        # 创建一个事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            executed_count, failed_count = loop.run_until_complete(async_send_to_nodes(execute_msg))
            return {"success": True, "message": f"已向 {executed_count} 个节点发送立即执行任务 {task_name} 的请求，失败 {failed_count} 个"}
        finally:
            loop.close()
    
    elif cmd == '-d':  # 删除任务
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 删除任务
        del all_tasks[task_name]
        
        # 删除数据文件
        file_path = os.path.join(DATA_DIR, f"task_{task_name}.json")
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.error(f"删除任务文件失败: {e}")
        
        # 通知所有节点删除任务
        delete_msg = {
            'type': 'delete_task',
            'task_name': task_name
        }
        
        # 创建一个事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            executed_count, failed_count = loop.run_until_complete(async_send_to_nodes(delete_msg))
            logger.info(f"已向 {executed_count} 个节点发送删除任务消息，失败 {failed_count} 个")
        finally:
            loop.close()
        
        return {"success": True, "message": f"任务 {task_name} 已删除"}
    
    elif cmd == '-a':  # 下发任务
        if len(parts) < 2:
            return {"success": False, "message": "缺少脚本名称"}
        
        # 获取脚本路径或名称
        full_script_path = parts[1]
        # 提取文件名（去掉路径部分）
        script_name = os.path.basename(full_script_path)
        
        # 验证脚本名称
        is_valid, error_msg = validate_script_name(script_name)
        if not is_valid:
            return {"success": False, "message": error_msg}
        
        # 解析任务名称（去掉时间后缀）
        task_name = '_'.join(script_name.split('_')[:-1])
        
        # 优先使用从客户端接收的脚本内容
        if script_content is None:
            # 如果客户端没有提供脚本内容，则尝试在服务器本地读取
            script_path = full_script_path
            try:
                with open(script_path, 'r', encoding='utf-8') as f:
                    script_content = f.read()
            except FileNotFoundError:
                return {"success": False, "message": f"脚本文件 {script_path} 不存在，且客户端未提供脚本内容"}
            except Exception as e:
                return {"success": False, "message": f"读取脚本文件失败: {e}"}
        
        # 解析执行间隔
        interval = parse_interval(script_name)
        if not interval:
            return {"success": False, "message": "无法从脚本名称解析执行间隔"}
        
        # 创建或更新任务
        all_tasks[task_name] = Task(task_name, script_content, interval)
        
        # 通知所有节点执行任务
        task_msg = {
            'type': 'task',
            'task_name': task_name,
            'script_content': script_content,
            'interval': interval
        }
        
        # 创建一个事件循环来运行异步函数
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            executed_count, failed_count = loop.run_until_complete(async_send_to_nodes(task_msg))
            logger.info(f"已向 {executed_count} 个节点发送任务消息，失败 {failed_count} 个")
        finally:
            loop.close()
        
        return {"success": True, "message": f"脚本 {script_name} 已上传并下发到 {len(connected_nodes)} 个节点"}
    
    elif cmd == '-c':  # 清除任务记录
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 清除结果
        all_tasks[task_name].results = {}
        save_task_results(task_name)
        
        return {"success": True, "message": f"任务 {task_name} 的记录已清除"}
    
    elif cmd == '-s':  # 显示脚本内容
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 获取原始脚本内容
        original_content = all_tasks[task_name].script_content
        # 获取执行间隔（秒）
        interval_seconds = all_tasks[task_name].interval
        # 将秒转换为更友好的格式（m表示分钟）
        interval_str = f"{interval_seconds // 60}m"
        # 在脚本开头添加注释掉的执行周期信息
        modified_content = f"task  {interval_str} \n{original_content}"
        
        return {"success": True, "data": modified_content}
    
    elif cmd == '-u':  # 上传脚本
        # 验证是否提供了脚本内容
        if not script_name or not script_content:
            return {"success": False, "message": "脚本内容缺失"}
        
        # 验证脚本名称
        is_valid, error_msg = validate_script_name(script_name)
        if not is_valid:
            return {"success": False, "message": error_msg}
        
        # 解析任务名称（去掉时间后缀）
        task_name = '_'.join(script_name.split('_')[:-1])
        
        # 解析执行间隔
        interval = parse_interval(script_name)
        if not interval:
            return {"success": False, "message": "无法从脚本名称解析执行间隔"}
        
        # 创建或更新任务
        all_tasks[task_name] = Task(task_name, script_content, interval)
        logger.info(f"用户 {username} 上传了脚本: {script_name}，任务名: {task_name}")
        
        # 保存脚本到文件系统（可选）
        scripts_dir = os.path.join(DATA_DIR, 'scripts')
        os.makedirs(scripts_dir, exist_ok=True)
        script_file_path = os.path.join(scripts_dir, script_name)
        try:
            with open(script_file_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            logger.info(f"脚本已保存到: {script_file_path}")
        except Exception as e:
            logger.error(f"保存脚本文件失败: {e}")
        
        # 通知所有节点执行任务
        for node_id, node in connected_nodes.items():
            # 直接使用原始脚本内容下发，不包含注释信息
            node.send_message({
                'type': 'task',
                'task_name': task_name,
                'script_content': script_content,
                'interval': interval
            })
        
        return {"success": True, "message": f"脚本 {script_name} 已上传并下发到 {len(connected_nodes)} 个节点"}
    
    else:
        return {"success": False, "message": f"未知命令: {cmd}"}

async def handle_client_command_async(command, username=None, script_name=None, script_content=None):
    """异步处理客户端命令"""
    parts = command.split()
    if len(parts) < 1:
        return {"success": False, "message": "命令格式错误"}
    
    cmd = parts[0]
    
    # 对于需要异步操作的命令，使用异步处理
    if cmd == '-n':  # 立即执行任务
        if len(parts) < 2:
            return {"success": False, "message": "缺少任务名称"}
        
        task_name = parts[1]
        if task_name not in all_tasks:
            return {"success": False, "message": f"任务 {task_name} 不存在"}
        
        # 异步发送到所有节点
        execute_msg = {
            'type': 'execute_task',
            'task_name': task_name
        }
        
        executed_count, failed_count = await async_send_to_nodes(execute_msg)
        return {"success": True, "message": f"已向 {executed_count} 个节点发送立即执行任务 {task_name} 的请求，失败 {failed_count} 个"}
    
    # 其他命令使用原有的同步处理
    return handle_client_command_original(command, username, script_name, script_content)

def handle_client_command_sync(command, username=None, script_name=None, script_content=None):
    """同步包装器，用于在同步环境中调用异步函数"""
    # 创建一个事件循环来运行异步函数
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 对于需要异步处理的命令，使用异步版本
        if command.startswith('-n'):
            # 先尝试获取现有事件循环，如果没有则创建新的
            try:
                current_loop = asyncio.get_event_loop()
                if current_loop.is_running():
                    # 如果有运行中的事件循环，使用run_coroutine_threadsafe
                    future = asyncio.run_coroutine_threadsafe(
                        handle_client_command_async(command, username, script_name, script_content), current_loop
                    )
                    return future.result()
            except RuntimeError:
                pass
                
            # 否则使用新的事件循环
            return loop.run_until_complete(handle_client_command_async(command, username, script_name, script_content))
        
        # 其他命令继续使用原有逻辑
        return handle_client_command_original(command, username, script_name, script_content)
    finally:
        loop.close()

# 重命名原始函数
handle_client_command_original = handle_client_command
# 替换handle_client_command为同步包装器
handle_client_command = handle_client_command_sync

def client_handler(client_socket, client_address):
    """处理客户端连接"""
    client_ip, client_port = client_address
    logger.info(f"新的客户端连接: {client_address}")
    
    # 初始化日志记录信息
    log_extra = {
        'username': 'unknown',
        'command': 'unknown',
        'success': 'failed',
        'client_ip': client_ip,
        'client_port': client_port
    }
    
    try:
        # 接收认证信息
        data = client_socket.recv(4096)
        if not data:
            return
        
        auth_data = json.loads(data.decode('utf-8'))
        username = auth_data.get('username', 'unknown')
        password = auth_data.get('password', '')
        command = auth_data.get('command', '')
        
        # 更新日志信息
        log_extra['username'] = username
        log_extra['command'] = command
        
        # 验证用户
        if not authenticate_user(username, password):
            response = {"success": False, "message": "认证失败"}
            client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
            logger.warning(f"客户端 {client_address} 认证失败: {username}")
            # 记录认证失败日志
            client_logger.info(f"认证失败: 密码错误", extra=log_extra)
            return
        
        logger.info(f"客户端 {client_address} 认证成功: {username}")
        
        # 处理命令，传递可能的脚本信息
        response = handle_client_command(
            command, 
            username,
            auth_data.get('script_name'),
            auth_data.get('script_content')
        )
        
        # 更新日志成功状态
        log_extra['success'] = 'success' if response.get('success', False) else 'failed'
        
        # 记录客户端操作日志
        operation_result = response.get('message', '') or ("成功" if response.get('success', False) else "失败")
        client_logger.info(f"操作结果: {operation_result}", extra=log_extra)
        
        # 发送响应
        client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
    
    except json.JSONDecodeError as e:
        logger.error(f"解析客户端消息失败: {e}")
        response = {"success": False, "message": "无效的请求格式"}
        client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
        # 记录格式错误日志
        client_logger.info(f"请求格式错误", extra=log_extra)
    except Exception as e:
        logger.error(f"处理客户端连接时出错: {e}")
        response = {"success": False, "message": f"服务器错误: {e}"}
        client_socket.sendall((json.dumps(response) + '\n').encode('utf-8'))
        # 记录服务器错误日志
        client_logger.info(f"服务器错误: {str(e)}", extra=log_extra)
    finally:
        client_socket.close()

def start_client_server():
    """启动客户端服务"""
    client_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    client_server.bind((SERVER_HOST, SERVER_PORT))
    client_server.listen(5)
    logger.info(f"客户端服务启动在 {SERVER_HOST}:{SERVER_PORT}")
    
    while True:
        try:
            client_socket, client_address = client_server.accept()
            # 为每个客户端创建新线程
            thread = threading.Thread(
                target=client_handler,
                args=(client_socket, client_address),
                daemon=True
            )
            thread.start()
        except Exception as e:
            logger.error(f"接受客户端连接时出错: {e}")

async def start_node_server():
    """启动节点服务（异步版本）"""
    server = await asyncio.start_server(
        handle_node, SERVER_HOST, NODE_PORT
    )
    
    addr = server.sockets[0].getsockname()
    logger.info(f"节点服务启动在 {addr[0]}:{addr[1]}")
    
    async with server:
        await server.serve_forever()

def cleanup_dead_nodes():
    """清理长时间未心跳的节点"""
    while True:
        current_time = time.time()
        for node_id, node in list(connected_nodes.items()):
            if current_time - node.last_heartbeat > 60:  # 超过60秒无心跳则认为离线
                logger.warning(f"节点 {node_id} 超过60秒未心跳，关闭连接")
                node.close()
        time.sleep(30)

async def main_async():
    """异步主函数"""
    logger.info("SuperAgent Server 启动")
    
    # 加载任务结果
    load_task_results()
    
    # 创建脚本目录
    os.makedirs('../scripts', exist_ok=True)
    
    # 启动清理协程
    asyncio.create_task(cleanup_dead_nodes_async())
    
    # 启动客户端服务器（保持同步以兼容现有代码）
    client_server_thread = threading.Thread(target=start_client_server, daemon=True)
    client_server_thread.start()
    
    # 启动节点服务（异步版本）
    await start_node_server()

async def cleanup_dead_nodes_async():
    """异步清理死亡节点"""
    CLEANUP_INTERVAL = 30  # 清理间隔（秒）
    NODE_TIMEOUT = 60  # 节点超时时间（秒）
    
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL)
        current_time = time.time()
        dead_nodes = []
        
        async with connected_nodes_lock:
            # 先收集所有死亡节点，然后再关闭，避免在迭代过程中修改集合
            nodes_to_check = list(connected_nodes.items())
            for node_id, node in nodes_to_check:
                if current_time - node.last_heartbeat > NODE_TIMEOUT:
                    dead_nodes.append((node_id, node.hostname))
                    try:
                        await node.close()
                    except Exception as e:
                        logger.error(f"关闭死亡节点 {node_id}({node.hostname}) 时出错: {e}")
            
        if dead_nodes:
            # 更详细的死亡节点信息日志
            dead_nodes_info = ", ".join([f"{node_id}({hostname})" for node_id, hostname in dead_nodes])
            logger.info(f"清理了 {len(dead_nodes)} 个死亡节点: {dead_nodes_info}")

def main():
    """主函数入口"""
    try:
        # 启动异步主函数
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("SuperAgent Server 正在关闭...")
    except Exception as e:
        logger.error(f"服务器错误: {e}")
    finally:
        logger.info("SuperAgent Server 已关闭")

if __name__ == '__main__':
    main()
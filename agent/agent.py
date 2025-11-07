#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控系统Agent端
负责执行服务端下发的脚本并回传执行结果
"""

import asyncio
import json
import os
import time
import threading
import logging
import subprocess
import re
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# 获取主机名
HOSTNAME = socket.gethostname()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='superagent_agent.log',
    handlers=[
        logging.FileHandler('superagent_agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('superagent-agent')

# 全局配置
SERVER_HOST = '192.168.123.178'  # 服务端地址
SERVER_PORT = 4568  # 节点连接端口
SCRIPT_DIR = '/opt/script/superagent/'  # 脚本存储目录
TASKS_FILE = os.path.join(SCRIPT_DIR, '.tasks.json')  # 任务持久化文件

# 节点ID
NODE_ID = None

# 存储任务信息
class Task:
    def __init__(self, task_name, script_content, interval):
        self.task_name = task_name
        self.script_content = script_content
        self.interval = interval
        self.timer = None
        self.script_path = os.path.join(SCRIPT_DIR, f"{task_name}.sh")
        self.should_stop = False  # 用于控制任务是否继续运行

# 所有任务
all_tasks = {}

# 创建线程池用于执行脚本
thread_pool = ThreadPoolExecutor(max_workers=10)

# 创建脚本目录
os.makedirs(SCRIPT_DIR, exist_ok=True)

class ScriptExecutor:
    """脚本执行器"""
    
    @staticmethod
    def save_script(task_name, script_content):
        """保存脚本到本地"""
        try:
            script_path = os.path.join(SCRIPT_DIR, f"{task_name}.sh")
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # 添加执行权限
            os.chmod(script_path, 0o755)
            logger.info(f"脚本 {task_name} 已保存到 {script_path}")
            return True, script_path
        except Exception as e:
            error_msg = f"保存脚本失败: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    @staticmethod
    def execute_script(script_path):
        """执行脚本并解析输出"""
        try:
            logger.info(f"执行脚本: {script_path}")
            
            # 执行脚本，使用shell=True以支持环境变量解析
            result = subprocess.run(
                script_path,
                shell=True,
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            output = result.stdout.strip()
            return output
            
        except subprocess.TimeoutExpired:
            error_msg = f"脚本执行超时（超过5分钟）"
            logger.error(error_msg)
            return error_msg
        except subprocess.CalledProcessError as e:
            error_msg = f"脚本执行失败，退出码: {e.returncode}\n错误输出: {e.stderr}"
            logger.error(error_msg)
            return error_msg
        except Exception as e:
            error_msg = f"执行脚本时发生异常: {e}"
            logger.error(error_msg)
            return error_msg
    
    @staticmethod
    def parse_script_output(output):
        """解析脚本输出，提取级别和值"""
        # 尝试匹配格式: 级别|值
        match = re.search(r'^([IWE])\|\s*(.*)$', output.strip())
        if match:
            level = match.group(1)
            value = match.group(2).strip()
            return level, value
        
        # 如果没有匹配，默认为O级别
        return 'O', output.strip()

# 保留原有的setup_task函数以兼容load_tasks
# 在load_tasks中会使用这个函数，但在实际运行时会被setup_task_async替代
# 当没有writer参数时，不会实际发送结果，只保存任务

def setup_task(task_name, script_content, interval):
    """设置任务（兼容旧代码）"""
    # 取消已存在的任务
    if task_name in all_tasks:
        cancel_task(task_name)
    
    # 保存脚本
    success, result = ScriptExecutor.save_script(task_name, script_content)
    if not success:
        logger.error(f"设置任务 {task_name} 失败: {result}")
        return False
    
    # 创建任务对象
    task = Task(task_name, script_content, interval)
    all_tasks[task_name] = task
    
    # 注意：这里不再启动实际的任务执行
    # 任务执行将在连接到服务器后通过asyncio启动
    
    # 更新持久化存储
    save_tasks()
    
    logger.info(f"任务 {task_name} 已设置，执行间隔: {interval}秒")
    return True

def save_tasks():
    """保存任务信息到本地文件"""
    try:
        tasks_data = {}
        for task_name, task in all_tasks.items():
            tasks_data[task_name] = {
                'script_content': task.script_content,
                'interval': task.interval
            }
        
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks_data, f, ensure_ascii=False, indent=2)
        logger.info(f"任务信息已保存到 {TASKS_FILE}")
    except Exception as e:
        logger.error(f"保存任务信息失败: {e}")

def load_tasks():
    """从本地文件加载任务信息"""
    if not os.path.exists(TASKS_FILE):
        logger.info("任务文件不存在，无需加载")
        return
    
    try:
        with open(TASKS_FILE, 'r', encoding='utf-8') as f:
            tasks_data = json.load(f)
        
        for task_name, task_info in tasks_data.items():
            setup_task(task_name, task_info['script_content'], task_info['interval'])
        logger.info(f"已从 {TASKS_FILE} 加载 {len(tasks_data)} 个任务")
    except Exception as e:
        logger.error(f"加载任务信息失败: {e}")

def cancel_task(task_name):
    """取消任务"""
    if task_name in all_tasks:
        task = all_tasks[task_name]
        task.should_stop = True  # 设置停止标志
        if task.timer:
            task.timer.cancel()
        # 删除脚本文件
        try:
            if os.path.exists(task.script_path):
                os.remove(task.script_path)
        except Exception as e:
            logger.error(f"删除脚本文件失败: {e}")
        del all_tasks[task_name]
        # 更新持久化存储
        save_tasks()
        logger.info(f"任务 {task_name} 已取消")

async def start_task_timer(task, writer):
    """异步启动任务定时器"""
    async def run_task():
        while not task.should_stop and task.task_name in all_tasks:
            try:
                # 在工作线程中执行脚本，避免阻塞事件循环
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(thread_pool, ScriptExecutor.execute_script, task.script_path)
                
                # 解析输出
                level, value = ScriptExecutor.parse_script_output(output)
                
                # 异步发送结果
                await send_task_result(task.task_name, level, value, writer)
                
                # 等待下一次执行
                await asyncio.sleep(task.interval)
            except Exception as e:
                logger.error(f"执行任务 {task.task_name} 时出错: {e}")
                # 出错后仍然等待，避免频繁重试
                if not task.should_stop and task.task_name in all_tasks:
                    await asyncio.sleep(task.interval)
    
    # 立即创建并启动任务协程
    asyncio.create_task(run_task())

async def send_task_result(task_name, level, value, writer):
    """异步发送任务执行结果到服务端"""
    try:
        message = {
            'type': 'task_result',
            'task_name': task_name,
            'timestamp': datetime.now().isoformat(),
            'level': level,
            'value': value,
            'hostname': HOSTNAME  # 添加主机名信息
        }
        
        # 异步发送数据
        writer.write((json.dumps(message) + '\n').encode('utf-8'))
        await writer.drain()
        logger.info(f"已发送任务 {task_name} 结果: {level} {value}")
    except Exception as e:
        logger.error(f"发送任务结果失败: {e}")

async def send_heartbeat(writer):
    """异步定期发送心跳"""
    while True:
        try:
            message = {'type': 'heartbeat', 'timestamp': time.time()}
            writer.write((json.dumps(message) + '\n').encode('utf-8'))
            await writer.drain()
            logger.debug("已发送心跳")
        except Exception as e:
            logger.error(f"发送心跳失败: {e}")
            break
        
        await asyncio.sleep(30)  # 每30秒发送一次心跳

async def handle_server_message(message, writer):
    """处理来自服务端的消息（异步版本）"""
    global NODE_ID
    
    msg_type = message.get('type')
    
    if msg_type == 'handshake':
        NODE_ID = message.get('node_id')
        logger.info(f"收到节点ID: {NODE_ID}")
    
    elif msg_type == 'heartbeat_response':
        logger.debug("收到心跳响应")
    
    elif msg_type == 'task':
        task_name = message.get('task_name')
        script_content = message.get('script_content')
        interval = message.get('interval')
        
        # 传递writer给setup_task
        if await setup_task_async(task_name, script_content, interval, writer):
            logger.info(f"成功接收任务: {task_name}")
    
    elif msg_type == 'delete_task':
        task_name = message.get('task_name')
        cancel_task(task_name)
    
    elif msg_type == 'tasks_sync':
        # 处理任务同步消息，用于比对本地任务和服务端任务
        server_tasks = message.get('tasks', [])
        server_task_names = set(server_tasks)
        
        # 删除本地有但服务端没有的任务
        for task_name in list(all_tasks.keys()):
            if task_name not in server_task_names:
                logger.info(f"服务端没有任务 {task_name}，删除本地任务")
                cancel_task(task_name)
    
    elif msg_type == 'execute_task':
        # 处理立即执行任务的消息
        task_name = message.get('task_name')
        if task_name in all_tasks:
            logger.info(f"收到立即执行任务的请求: {task_name}")
            
            # 异步执行任务
            asyncio.create_task(execute_task_immediately(task_name, writer))
        else:
            logger.warning(f"请求执行不存在的任务: {task_name}")
    
    else:
        logger.warning(f"未知消息类型: {msg_type}")

async def execute_task_immediately(task_name, writer):
    """异步立即执行任务"""
    try:
        task = all_tasks.get(task_name)
        if task:
            # 在工作线程中执行脚本
            loop = asyncio.get_event_loop()
            output = await loop.run_in_executor(thread_pool, ScriptExecutor.execute_script, task.script_path)
            
            # 解析输出
            level, value = ScriptExecutor.parse_script_output(output)
            
            # 异步发送结果
            await send_task_result(task_name, level, value, writer)
    except Exception as e:
        logger.error(f"立即执行任务 {task_name} 时出错: {e}")

async def setup_task_async(task_name, script_content, interval, writer):
    """异步设置任务"""
    # 取消已存在的任务
    if task_name in all_tasks:
        cancel_task(task_name)
    
    # 保存脚本（使用线程池避免阻塞事件循环）
    loop = asyncio.get_event_loop()
    success, result = await loop.run_in_executor(
        thread_pool, 
        lambda: ScriptExecutor.save_script(task_name, script_content)
    )
    
    if not success:
        logger.error(f"设置任务 {task_name} 失败: {result}")
        return False
    
    # 创建任务对象
    task = Task(task_name, script_content, interval)
    all_tasks[task_name] = task
    
    # 异步启动定时任务
    await start_task_timer(task, writer)
    
    # 更新持久化存储（使用线程池）
    await loop.run_in_executor(thread_pool, save_tasks)
    
    logger.info(f"任务 {task_name} 已设置，执行间隔: {interval}秒")
    return True

async def connect_to_server():
    """异步连接到服务端并保持通信"""
    while True:
        try:
            logger.info(f"尝试连接到服务端: {SERVER_HOST}:{SERVER_PORT}")
            
            # 异步创建socket连接
            reader, writer = await asyncio.open_connection(
                SERVER_HOST, SERVER_PORT
            )
            logger.info("成功连接到服务端")
            
            # 启动心跳协程
            heartbeat_task = asyncio.create_task(send_heartbeat(writer))
            
            # 处理来自服务端的消息
            buffer = ''
            try:
                while True:
                    # 异步读取数据
                    data = await reader.read(4096)
                    if not data:
                        logger.warning("服务端连接已关闭")
                        break
                    
                    # 处理可能的多条消息
                    buffer += data.decode('utf-8')
                    while '\n' in buffer:
                        line, buffer = buffer.split('\n', 1)
                        if line.strip():
                            try:
                                message = json.loads(line)
                                # 异步处理消息
                                await handle_server_message(message, writer)
                            except json.JSONDecodeError as e:
                                logger.error(f"解析消息失败: {e}")
            except Exception as e:
                logger.error(f"处理消息时出错: {e}")
            finally:
                # 取消心跳任务
                heartbeat_task.cancel()
                # 关闭连接
                writer.close()
                await writer.wait_closed()
                
                # 连接断开时停止所有任务
                for task_name, task in all_tasks.items():
                    task.should_stop = True
                logger.info("连接断开，已停止所有任务")
                
        except ConnectionRefusedError:
            logger.warning(f"无法连接到服务端，稍后重试")
        except Exception as e:
            logger.error(f"连接出错: {e}")
        
        # 等待重试
        await asyncio.sleep(10)

async def main_async():
    """异步主函数"""
    logger.info("SuperAgent Agent 启动")
    
    # 创建脚本目录
    os.makedirs(SCRIPT_DIR, exist_ok=True)
    
    # 从本地加载任务
    # 注意：这里只加载任务信息，实际执行会在连接服务器后启动
    load_tasks()
    
    # 异步连接到服务端
    await connect_to_server()

if __name__ == '__main__':
    # 运行异步主函数
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在退出...")
        # 取消所有任务
        for task_name in list(all_tasks.keys()):
            cancel_task(task_name)
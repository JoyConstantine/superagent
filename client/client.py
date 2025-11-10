#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
监控系统客户端
用于向服务端发送指令并接收执行结果
"""

import socket
import json
import sys
import argparse
import getpass
import logging
import os

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('superagent-client')

# 配置
SERVER_HOST = '101.43.69.41'
SERVER_PORT = 20257
TIMEOUT = 30

class Client:
    """客户端主类"""
    
    def __init__(self, server_host=SERVER_HOST, server_port=SERVER_PORT, username=None, password=None):
        self.server_host = server_host
        self.server_port = server_port
        self.username = username
        self.password = password
    
    def connect(self, command):
        """连接到服务端并发送命令"""
        try:
            # 检查是否为上传脚本命令或下发任务命令
            is_upload = command.startswith('-u ')
            is_add_task = command.startswith('-a ')
            script_path = None
            script_name = None
            script_content = None
            
            if is_upload or is_add_task:
                # 提取脚本路径
                script_path = command.split(' ', 1)[1]
                # 获取脚本文件名
                script_name = os.path.basename(script_path)
                
                # 读取脚本内容
                try:
                    with open(script_path, 'r', encoding='utf-8') as f:
                        script_content = f.read()
                    logger.info(f"已读取脚本文件: {script_path}")
                except Exception as e:
                    logger.error(f"读取脚本文件失败: {e}")
                    return {'success': False, 'message': f"读取脚本文件失败: {e}"}
            
            # 创建socket连接
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)  # 设置超时
            sock.connect((self.server_host, self.server_port))
            
            # 准备认证和命令数据
            auth_data = {
                'username': self.username,
                'password': self.password,
                'command': command
            }
            
            # 如果是上传脚本或下发任务，添加脚本内容和名称
            if is_upload or is_add_task:
                auth_data['script_name'] = script_name
                auth_data['script_content'] = script_content
            
            # 确保数据可以正确JSON序列化
            try:
                json_data = json.dumps(auth_data)
                # 发送数据
                sock.sendall((json_data + '\n').encode('utf-8'))
                logger.info(f"已成功序列化并发送数据，命令: {command}")
            except Exception as e:
                logger.error(f"JSON序列化失败: {e}")
                return {'success': False, 'message': f"构建请求数据失败: {e}"}
            
            # 接收响应
            data = b''
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
                # 检查是否收到完整消息（以\n结尾）
                if b'\n' in data:
                    break
            
            if data:
                response = json.loads(data.decode('utf-8').strip())
                return response
            else:
                return {'success': False, 'message': '未收到服务端响应'}
        
        except ConnectionRefusedError:
            logger.error(f"无法连接到服务端: {self.server_host}:{self.server_port}")
            return {'success': False, 'message': f"无法连接到服务端，请检查服务端是否运行在 {self.server_host}:{self.server_port}"}
        except json.JSONDecodeError:
            logger.error("解析服务端响应失败")
            return {'success': False, 'message': '解析服务端响应失败'}
        except socket.timeout:
            logger.error("连接超时")
            return {'success': False, 'message': '连接超时'}
        except Exception as e:
            logger.error(f"连接服务端时出错: {e}")
            return {'success': False, 'message': f"连接服务端时出错: {e}"}
        finally:
            if 'sock' in locals():
                sock.close()

def parse_arguments():
    """解析命令行参数"""
    # 创建主解析器
    parser = argparse.ArgumentParser(
        prog='client',
        description='监控系统客户端 - 用于向服务端发送指令',
        epilog='示例: client 192.168.1.1:4567 --user=admin --passwd="rL1|aB2#oE2!kR4~aC2<" -t check_kuaishou_cpu -I'
    )
    
    # 位置参数：服务器地址和端口
    parser.add_argument(
        'server', 
        nargs='?',
        default=f"{SERVER_HOST}:{SERVER_PORT}",
        help=f'服务端地址和端口 (默认: {SERVER_HOST}:{SERVER_PORT})'
    )
    
    # 认证参数
    parser.add_argument('--user', required=True, help='用户名')
    # 使用store_true=False以确保特殊字符能被正确处理
    parser.add_argument('--passwd', required=True, help='密码，建议使用双引号包裹包含特殊字符的密码')
    
    # 功能参数（互斥组）
    group = parser.add_mutually_exclusive_group(required=True)
    
    # 查询任务结果
    group.add_argument(
        '-t', '--task', 
        nargs='+',
        help='查询任务结果，格式: -t task_name [-I]'
    )
    
    # 列出所有任务
    group.add_argument(
        '-l', '--list', 
        action='store_true',
        help='列出所有任务'
    )
    
    # 删除任务
    group.add_argument(
        '-d', '--delete',
        help='删除任务'
    )
    
    # 下发任务
    group.add_argument(
        '-a', '--add',
        help='下发任务，指定脚本名称'
    )
    
    # 清除任务记录
    group.add_argument(
        '-c', '--clear',
        help='清除任务记录'
    )
    
    # 显示脚本内容
    group.add_argument(
        '-s', '--script',
        help='显示脚本内容'
    )
    
    # 上传脚本
    group.add_argument(
        '-u', '--upload',
        help='上传脚本文件'
    )
    
    # 立即执行任务
    group.add_argument(
        '-n', '--now',
        help='立即执行任务，格式: -n task_name'
    )
    
    return parser.parse_args()

def build_command(args):
    """构建发送给服务端的命令字符串"""
    if args.task:
        # 构建任务查询命令
        cmd_parts = ['-t'] + args.task
        return ' '.join(cmd_parts)
    elif args.list:
        return '-l'
    elif args.delete:
        return f'-d {args.delete}'
    elif args.add:
        return f'-a {args.add}'
    elif args.clear:
        return f'-c {args.clear}'
    elif args.script:
        return f'-s {args.script}'
    elif args.upload:
        return f'-u {args.upload}'
    elif args.now:
        return f'-n {args.now}'
    return ''

def parse_server_address(server_str):
    """解析服务端地址和端口"""
    try:
        if ':' in server_str:
            host, port = server_str.split(':', 1)
            return host, int(port)
        else:
            # 只有主机名，使用默认端口
            return server_str, SERVER_PORT
    except:
        # 解析失败，使用默认值
        return SERVER_HOST, SERVER_PORT

def main():
    """主函数"""
    try:
        # 解析命令行参数
        args = parse_arguments()
        
        # 解析服务端地址
        server_host, server_port = parse_server_address(args.server)
        
        # 构建命令
        command = build_command(args)
        
        # 处理密码中的转义字符 - 移除可能的多余反斜杠
        password = args.passwd
        # 处理在shell中被转义的特殊字符
        password = password.replace('\\|', '|').replace('\\#', '#').replace('\\!', '!').replace('\\~', '~').replace('\\<', '<')
        
        # 创建客户端并连接
        client = Client(server_host, server_port, args.user, password)
        response = client.connect(command)
        
        # 处理响应
        if response['success']:
            if 'data' in response:
                # 显示数据
                if isinstance(response['data'], list):
                    for line in response['data']:
                        print(line)
                else:
                    print(response['data'])
            elif 'message' in response:
                print(response['message'])
            return 0
        else:
            print(f"错误: {response.get('message', '未知错误')}")
            return 1
    
    except KeyboardInterrupt:
        print("\n操作已取消")
        return 130
    except Exception as e:
        logger.error(f"客户端运行出错: {e}")
        print(f"客户端错误: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
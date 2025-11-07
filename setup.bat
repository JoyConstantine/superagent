@echo off
REM SuperAgent 环境设置脚本
REM 用于在 Windows 系统上设置运行环境

cls
echo ===== SuperAgent 环境设置 =====

REM 检查 Python 版本
echo 检查 Python 版本...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: 未找到 Python。请安装 Python 3.6 或更高版本。
    pause
    exit /b 1
)

REM 获取 Python 版本
for /f "tokens=2" %%i in ('python --version') do set PYTHON_VERSION=%%i
for /f "tokens=1 delims=." %%a in ("%PYTHON_VERSION%") do set PYTHON_MAJOR=%%a
for /f "tokens=2 delims=." %%b in ("%PYTHON_VERSION%") do set PYTHON_MINOR=%%b

REM 检查版本是否满足要求
if %PYTHON_MAJOR% lss 3 (    
    echo 错误: 需要 Python 3.6 或更高版本，当前版本为 %PYTHON_VERSION%
    pause
    exit /b 1
) 
if %PYTHON_MAJOR% equ 3 if %PYTHON_MINOR% lss 6 (
    echo 错误: 需要 Python 3.6 或更高版本，当前版本为 %PYTHON_VERSION%
    pause
    exit /b 1
)

echo Python 版本检查通过: %PYTHON_VERSION%

REM 创建必要的目录
echo 创建必要的目录...
mkdir server\data 2>nul || echo 目录已存在
type nul > server\data\.gitkeep 2>nul || echo 文件已存在

mkdir agent\logs 2>nul || echo 目录已存在
type nul > agent\logs\.gitkeep 2>nul || echo 文件已存在

mkdir client\logs 2>nul || echo 目录已存在
type nul > client\logs\.gitkeep 2>nul || echo 文件已存在

mkdir config 2>nul || echo 目录已存在

REM 创建 super 快捷命令脚本（Windows 批处理文件）
echo 创建 super.bat 快捷命令脚本...
set "SCRIPT_DIR=%~dp0"

( 
    echo @echo off
    echo REM SuperAgent 快捷命令
    echo set "CLIENT_PY=%SCRIPT_DIR:\=\\%client\\client.py"
    echo python "%%CLIENT_PY%%" 192.168.123.178:4567 --user=admin --passwd="rL1^|aB2#oE2!kR4~aC2^<" %%*
) > "%SCRIPT_DIR%super.bat"

echo super.bat 已创建在项目根目录

REM 创建使用说明文件
echo 创建使用说明文件...
( 
    echo SuperAgent 使用说明
    echo ===================
    echo.
    echo 1. 启动服务端:
    echo    cd server
    echo    python server.py
    echo.
    echo 2. 启动节点代理（在每个被监控节点上）:
    echo    cd agent
    echo    python agent.py
    echo.
    echo 3. 使用客户端命令（通过 super.bat）:
    echo    super -l       # 列出所有任务
    echo    super -t taskname -I  # 查询 INFO 级别结果
    echo    super -a script.sh  # 下发任务
    echo    super -d taskname  # 删除任务
    echo    super -c taskname  # 清除任务记录
    echo    super -s taskname  # 查看脚本内容
    echo.
    echo 4. 查看日志:
    echo    server\superagent_server.log
    echo    agent\superagent_agent.log
    echo    client\superagent_client.log
    echo.
    echo 注意事项:
    echo 1. 确保服务端、节点代理和客户端之间的网络连接正常
    echo 2. 在节点服务器上需要创建脚本目录: mkdir C:\opt\script\superagent\
    echo 3. 配置文件已自动创建，您可以根据需要修改 config\config.json 中的配置
) > "%SCRIPT_DIR%使用说明.txt"

echo 使用说明.txt 已创建在项目根目录

REM 显示完成信息
echo.
echo ===== 设置完成 =====
echo 1. 服务端启动脚本: server\server.py
if exist "%SCRIPT_DIR%super.bat" (
    echo 2. 客户端快捷命令: super.bat
    echo    使用方法: 双击 super.bat 或在命令行中运行 super 参数
) else (
    echo 2. 客户端命令: python client\client.py [参数]
)
echo 3. 详细使用说明: 使用说明.txt

REM 添加到环境变量的建议
echo.
echo 提示: 若要在任意目录使用 super 命令，请将项目目录添加到系统环境变量 PATH

echo.
pause
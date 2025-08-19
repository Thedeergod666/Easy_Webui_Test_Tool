@echo off
rem v1.0.0
rem 无论从哪里运行此脚本，都先将当前目录切换到脚本所在的目录。
cd /d %~dp0

chcp 936 > nul
setlocal

echo =======================================================
echo           自动化测试框架环境一键安装脚本
echo =======================================================
echo.

rem 定义镜像源地址
set PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

rem 检查 Python 环境
echo 正在检查 Python 环境...
python --version > nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未在本机找到 Python。请从官网 python.org 下载并安装 Python 3.8+。
    pause
    exit /b
)
echo Python 已安装。

rem 创建虚拟环境
echo.
echo 正在创建 Python 虚拟环境 (.venv)...
if not exist .venv (
    python -m venv .venv
)
echo 虚拟环境已创建。

rem ▼▼▼【新功能：升级pip】▼▼▼
echo.
echo 正在使用清华镜像源升级 pip 工具...
call .\.venv\Scripts\activate.bat && python -m pip install --upgrade pip -i %PIP_INDEX_URL%
if %errorlevel% neq 0 (
    echo [警告] pip 升级失败，将继续使用当前版本。
) else (
    echo pip 已成功升级到最新版本。
)

rem 激活虚拟环境并使用镜像源安装依赖
echo.
echo 正在使用清华镜像源安装所有项目依赖库 (可能需要几分钟)...
call .\.venv\Scripts\activate.bat && pip install -r requirements.txt -i %PIP_INDEX_URL%
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败。请检查网络或联系框架管理员。
    pause
    exit /b
)
echo 所有依赖库已安装成功！

rem 安装 Playwright 浏览器驱动
echo.
echo 正在下载 Playwright 浏览器驱动 (这可能需要较长时间，请耐心等待)...
call .\.venv\Scripts\activate.bat && playwright install
if %errorlevel% neq 0 (
    echo [错误] 浏览器驱动下载失败。请检查网络或联系框架管理员。
    pause
    exit /b
)
echo 浏览器驱动已成功安装！

echo.
echo =======================================================
echo           环境已准备就绪! 您可以运行测试了!
echo =======================================================
echo.
pause
endlocal

@echo off
chcp 65001 > nul
cd /d "%~dp0"

REM 激活虚拟环境
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
) else (
    echo 警告: 未找到虚拟环境，将使用全局Python环境
)

REM 启动主菜单
echo ========================================
echo   自动化测试与Codegen工具主菜单 (Windows)
echo ========================================
python framework/utils/main.py %*
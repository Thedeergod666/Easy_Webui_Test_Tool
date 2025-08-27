#!/bin/bash
# -*- coding: utf-8 -*-

# 无论从哪里运行此脚本，都先将当前目录切换到脚本所在的目录。
cd "$(dirname "$0")"

# 激活虚拟环境
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "警告: 未找到虚拟环境，将使用全局Python环境"
fi

# 启动主菜单
echo "========================================"
echo "   Easy_Webui_Test_Tool (Linux/macOS)"
echo "========================================"
python3 framework/utils/main.py "$@"
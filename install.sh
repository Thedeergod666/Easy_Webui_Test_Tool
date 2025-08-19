#!/bin/bash
# -*- coding: utf-8 -*-
# 无论从哪里运行此脚本，都先将当前目录切换到脚本所在的目录。
# v1.0.0
cd "$(dirname "$0")"

echo "======================================================="
echo "          自动化测试框架环境一键安装脚本 (macOS/Linux)"
echo "======================================================="
echo

# 定义镜像源地址
PIP_INDEX_URL="https://pypi.tuna.tsinghua.edu.cn/simple"

# 检查 Python 环境
echo "正在检查 Python 环境..."
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未在本机找到 python3。请先安装 Python 3.8+。"
    exit 1
fi
echo "Python 3 已安装。"

# 创建虚拟环境
echo
echo "正在创建 Python 虚拟环境 (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
echo "虚拟环境已创建。"

# 激活虚拟环境并升级pip
echo
echo "正在使用清华镜像源升级 pip 工具..."
source .venv/bin/activate && python3 -m pip install --upgrade pip -i "$PIP_INDEX_URL"
if [ $? -ne 0 ]; then
    echo "[警告] pip 升级失败，将继续使用当前版本。"
fi

# 安装依赖
echo
echo "正在使用清华镜像源安装所有项目依赖库..."
pip install -r requirements.txt -i "$PIP_INDEX_URL"
if [ $? -ne 0 ]; then
    echo "[错误] 依赖安装失败。请检查网络或联系框架管理员。"
    exit 1
fi
echo "所有依赖库已安装成功！"

# 安装 Playwright 浏览器驱动
echo
echo "正在下载 Playwright 浏览器驱动..."
playwright install
if [ $? -ne 0 ]; then
    echo "[错误] 浏览器驱动下载失败。请检查网络或联系框架管理员。"
    exit 1
fi
echo "浏览器驱动已成功安装！"

echo
echo "======================================================="
echo "          环境已准备就绪! 您可以运行测试了!"
echo "======================================================="
echo
# 在shell中，脚本执行完会自动退出，通常不需要pause

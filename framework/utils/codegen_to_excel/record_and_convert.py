#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Playwright录制并转换工具
此脚本用于启动Playwright Codegen录制，并将录制的代码自动转换为Excel测试用例文件
"""

import os
import sys
import json
import subprocess
import time
import argparse
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def start_playwright_codegen(output_file):
    """启动Playwright Codegen录制"""
    print(f"--- 启动Playwright Codegen录制 ---")
    print(f"  > 录制文件将保存到: {output_file}")
    print(f"  > 请在打开的浏览器窗口中执行您要录制的操作")
    print(f"  > 录制完成后，请关闭浏览器窗口")
    
    # 确保输出文件存在，如果不存在则创建一个空文件
    output_path = Path(output_file)
    if not output_path.exists():
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("# 录制文件\n", encoding="utf-8")
        print(f"  > 已创建空的录制文件: {output_file}")
    
    # 使用相对路径
    relative_output_file = output_path.relative_to(project_root)
    
    # 构建命令
    cmd = [
        sys.executable, "-m", "playwright", "codegen",
        "--output", str(relative_output_file),
        "--target", "python-pytest"
    ]
    
    try:
        # 启动Playwright Codegen
        process = subprocess.Popen(cmd, cwd=project_root)
        process.wait()
        return process.returncode == 0
    except Exception as e:
        print(f"[错误] 启动Playwright Codegen失败: {e}")
        return False

def convert_to_excel(py_file, flow_name, sheet_name="Sheet1", browser="chromium", enabled=True, update_config=True):
    """调用codegen_to_excel.py脚本进行转换"""
    print(f"--- 开始转换录制文件为Excel测试用例 ---")
    
    # 构建转换脚本路径
    converter_script = project_root / "framework" / "utils" / "codegen_to_excel" / "codegen_to_excel.py"
    
    # 构建输出Excel文件路径
    output_excel = project_root / "test_data" / f"{flow_name}.xlsx"
    
    # 构建命令
    cmd = [
        sys.executable, str(converter_script),
        py_file, flow_name,
        "--sheet-name", sheet_name,
        "--browser", browser
    ]
    
    if not enabled:
        cmd.append("--disabled")
    
    if not update_config:
        cmd.append("--no-config-update")
    
    try:
        # 执行转换
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  > 转换成功完成")
            print(f"  > Excel文件已生成: {output_excel}")
            # 解析输出以获取最终的Sheet名称
            output_lines = result.stdout.split('\n')
            final_sheet_name = "Sheet1"  # 默认值
            for line in output_lines:
                if "Sheet 名称:" in line:
                    final_sheet_name = line.split("Sheet 名称:")[1].strip()
                    break
            print(f"  > Sheet 名称: {final_sheet_name}")
            return True
        else:
            print(f"[错误] 转换失败:")
            print(result.stdout)
            print(result.stderr)
            # 尝试解析Sheet名称，即使转换失败
            output_lines = result.stdout.split('\n')
            final_sheet_name = "Sheet1"  # 默认值
            for line in output_lines:
                if "Sheet 名称:" in line:
                    final_sheet_name = line.split("Sheet 名称:")[1].strip()
                    break
            if final_sheet_name != "Sheet1":  # 如果找到了Sheet名称
                print(f"  > Sheet 名称: {final_sheet_name}")
            return False
    except Exception as e:
        print(f"[错误] 执行转换脚本失败: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Playwright录制并转换工具")
    parser.add_argument("flow_name", help="新测试流程的名称 (将作为Excel文件名)")
    parser.add_argument("--sheet-name", default="Sheet1", help="指定Excel中的sheet名称 (默认: Sheet1)")
    parser.add_argument("--browser", default="chromium", help="指定测试浏览器 (默认: chromium)")
    parser.add_argument("--disabled", action="store_true", help="将新流程设置为禁用状态")
    parser.add_argument("--no-config-update", action="store_true", help="不自动更新test_config.json配置文件")
    args = parser.parse_args()
    
    print(f"=== Playwright录制并转换工具 ===")
    
    # 确定录制文件路径
    latest_py_file = project_root / "test_data" / "latest_auto_test_flow.py"
    
    # 启动录制
    if start_playwright_codegen(str(latest_py_file)):
        print(f"  > 录制已完成，文件已保存到: {latest_py_file}")
        
        # 检查录制文件是否存在
        if latest_py_file.exists():
            # 执行转换
            if convert_to_excel(
                str(latest_py_file), 
                args.flow_name, 
                args.sheet_name, 
                args.browser, 
                not args.disabled, 
                not args.no_config_update
            ):
                print(f"=== 所有操作已完成 ===")
                return 0
            else:
                print(f"[错误] 转换过程中出现错误")
                return 1
        else:
            print(f"[错误] 录制文件未生成: {latest_py_file}")
            return 1
    else:
        print(f"[错误] 录制过程中出现错误")
        return 1

if __name__ == "__main__":
    sys.exit(main())
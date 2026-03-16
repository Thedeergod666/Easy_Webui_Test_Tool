#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一功能执行器
此模块提供统一的功能调用接口，支持CICD模式和交互模式下的功能执行
"""

import os
import sys
import argparse

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.run_tests.runner import run_tests, cleanup_temp_files
from framework.utils.ui.view_test_cases import view_test_cases
from framework.utils.config_workflow import (
    initialize_test_config,
    print_workflow_result,
    validate_test_config,
)


COMMAND_ALIASES = {
    "list": "9",
    "cases": "9",
    "cleanup": "10",
    "clean": "10",
    "init": "11",
    "validate": "12",
}

class FunctionExecutor:
    """统一功能执行器"""

    @staticmethod
    def normalize_func_id(func_id):
        """将文本别名归一化为菜单功能ID。"""
        if func_id is None:
            return None
        return COMMAND_ALIASES.get(str(func_id).lower(), str(func_id).lower())
    
    @staticmethod
    def execute_function(func_id, args=None, ci_mode=False):
        """
        执行指定功能
        
        Args:
            func_id: 功能ID (对应菜单选项编号)
            args: 功能参数
            ci_mode: 是否为CI/CD模式
        """
        func_id = FunctionExecutor.normalize_func_id(func_id)

        if func_id in ["1", "2", "3", "4", "5", "6"]:
            # 测试执行模式
            if args:
                return run_tests(f"{func_id} {args}", ci_mode=ci_mode)
            return run_tests(func_id, ci_mode=ci_mode)
                
        elif func_id == "7":
            # Codegen: 从现有Python文件转换
            if ci_mode:
                # 在CI/CD模式下，需要从args获取参数
                if args and hasattr(args, 'py_file'):
                    # 直接调用codegen_to_excel模块的功能
                    from framework.utils.codegen_to_excel.codegen_to_excel import convert_py_to_excel, update_test_config
                    output_excel_path = os.path.join(project_root, 'test_data', f"{args.flow_name}.xlsx")
                    
                    # 执行转换
                    result = convert_py_to_excel(args.py_file, output_excel_path, args.sheet_name)
                    if result[0]:  # 检查成功状态
                        final_sheet_name = result[1]  # 获取最终的Sheet名称
                        print(f"  > Excel 文件已成功生成: {output_excel_path}")
                        print(f"  > Sheet 名称: {final_sheet_name}")
                        
                        # 更新配置文件
                        if update_test_config(output_excel_path, args.flow_name, final_sheet_name, args.browser, not args.disabled):
                            print(f"  > test_config.json 配置文件已更新")
                            return 0
                        else:
                            print(f"  > test_config.json 配置文件更新失败")
                            return 1
                    else:
                        print(f"--- 转换失败 ---")
                        return 1
                else:
                    print("[错误] Codegen命令缺少必要参数")
                    return 1
            else:
                from framework.utils.ui.codegen_ui import convert_from_file
                convert_from_file()
            return 0
                
        elif func_id == "8":
            # Codegen: 启动Playwright录制并转换
            if ci_mode:
                # 在CI/CD模式下，需要从args获取参数
                if args and hasattr(args, 'flow_name'):
                    # 直接调用record_and_convert模块的功能
                    from framework.utils.codegen_to_excel.record_and_convert import convert_to_excel
                    py_file = os.path.join(project_root, 'test_data', 'latest_auto_test_flow.py')
                    
                    # 执行转换
                    if convert_to_excel(
                        py_file,
                        args.flow_name,
                        args.sheet_name,
                        args.browser,
                        not args.disabled,
                        True  # 更新配置文件
                    ):
                        print(f"=== 所有操作已完成 ===")
                        return 0
                    else:
                        print(f"[错误] 转换过程中出现错误")
                        return 1
                else:
                    print("[错误] Codegen录制命令缺少必要参数")
                    return 1
            else:
                from framework.utils.ui.codegen_ui import record_and_convert
                record_and_convert()
            return 0
                
        elif func_id == "9":
            # test_config.json用例快速查看
            return view_test_cases(non_interactive=ci_mode)
            
        elif func_id == "10":
            # 清理残留临时文件
            return cleanup_temp_files(ci_mode=ci_mode)

        elif func_id == "11":
            result = initialize_test_config(project_root)
            print_workflow_result(result)
            return result.exit_code

        elif func_id == "12":
            result = validate_test_config(project_root)
            print_workflow_result(result)
            return result.exit_code
            
        else:
            print(f"未知功能ID: {func_id}")
            return 1

    @staticmethod
    def parse_command_args(args):
        """
        解析命令行参数
        
        Args:
            args: 命令行参数列表
            
        Returns:
            tuple: (func_id, parsed_args)
        """
        if not args:
            return None, None
            
        func_id = FunctionExecutor.normalize_func_id(args[0])
        func_args = args[1:] if len(args) > 1 else []
        
        # 根据功能ID解析特定参数
        if func_id in ["1", "2", "3", "4", "5", "6"]:
            # 测试执行模式参数
            if func_args:
                return func_id, " ".join(func_args)
            else:
                return func_id, None
                
        elif func_id == "7":
            # Codegen: 从现有Python文件转换
            parser = argparse.ArgumentParser()
            parser.add_argument("--py-file", required=True, help="Python文件路径")
            parser.add_argument("--flow-name", required=True, help="流程名称")
            parser.add_argument("--sheet-name", default="Sheet1", help="Sheet名称")
            parser.add_argument("--browser", default="chromium", help="浏览器类型")
            parser.add_argument("--disabled", action="store_true", help="是否禁用")
            
            parsed_args = parser.parse_args(func_args)
            return func_id, parsed_args
            
        elif func_id == "8":
            # Codegen: 启动Playwright录制并转换
            parser = argparse.ArgumentParser()
            parser.add_argument("--flow-name", required=True, help="流程名称")
            parser.add_argument("--sheet-name", default="Sheet1", help="Sheet名称")
            parser.add_argument("--browser", default="chromium", help="浏览器类型")
            parser.add_argument("--disabled", action="store_true", help="是否禁用")
            
            parsed_args = parser.parse_args(func_args)
            return func_id, parsed_args
            
        elif func_id in ["9", "10", "11", "12"]:
            return func_id, None

        else:
            # 其他功能不需要特殊参数解析
            return func_id, None

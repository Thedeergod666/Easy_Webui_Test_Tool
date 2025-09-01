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

class FunctionExecutor:
    """统一功能执行器"""
    
    @staticmethod
    def execute_function(func_id, args=None, ci_mode=False):
        """
        执行指定功能
        
        Args:
            func_id: 功能ID (对应菜单选项编号)
            args: 功能参数
            ci_mode: 是否为CI/CD模式
        """
        if func_id in ["1", "2", "3", "4", "5", "6"]:
            # 测试执行模式
            if args:
                run_tests(f"{func_id} {args}", ci_mode=ci_mode)
            else:
                run_tests(func_id, ci_mode=ci_mode)
                
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
                        else:
                            print(f"  > test_config.json 配置文件更新失败")
                    else:
                        print(f"--- 转换失败 ---")
                else:
                    print("[错误] Codegen命令缺少必要参数")
            else:
                from framework.utils.ui.codegen_ui import convert_from_file
                convert_from_file()
                
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
                    else:
                        print(f"[错误] 转换过程中出现错误")
                else:
                    print("[错误] Codegen录制命令缺少必要参数")
            else:
                from framework.utils.ui.codegen_ui import record_and_convert
                record_and_convert()
                
        elif func_id == "9":
            # test_config.json用例快速查看
            # 在CICD模式下传递参数
            if ci_mode:
                import sys
                sys.argv.append("ci")
                view_test_cases()
                sys.argv.pop()
            else:
                view_test_cases()
            
        elif func_id == "10":
            # 清理残留临时文件
            cleanup_temp_files(ci_mode=ci_mode)
            
        else:
            print(f"未知功能ID: {func_id}")

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
            
        func_id = args[0]
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
            
        else:
            # 其他功能不需要特殊参数解析
            return func_id, None
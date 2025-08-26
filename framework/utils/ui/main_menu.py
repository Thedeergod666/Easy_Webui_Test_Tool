# framework/utils/ui/main_menu.py
import os
import sys

# 将项目根目录添加到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.run_tests.runner import run_tests
from framework.utils.ui.codegen_ui import convert_from_file, record_and_convert
import json

def view_test_cases():
    """查看test_config.json中的测试用例"""
    # 修正路径计算，确保指向项目根目录下的test_data文件夹
    actual_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    config_path = os.path.join(actual_project_root, 'test_data', 'test_config.json')
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"[错误] 找不到配置文件: {config_path}")
        input("按回车键继续...")
        return
    except json.JSONDecodeError:
        print(f"[错误] 配置文件格式错误: {config_path}")
        input("按回车键继续...")
        return
    
    test_flows = config.get('test_flows', [])
    if not test_flows:
        print("[信息] 配置文件中没有找到测试用例")
        input("按回车键继续...")
        return
    
    print("\n=== test_config.json 用例快速查看 ===")
    print(f"总共找到 {len(test_flows)} 个测试用例:")
    print()
    
    total_count = len(test_flows)
    for i, flow in enumerate(test_flows, 1):
        # 计算负编号
        negative_index = i - total_count - 1
        
        # 获取状态图标
        status_icon = "✓" if flow.get('enabled', True) else "✗"
        
        # 获取浏览器类型
        browser = flow.get('browser', 'chromium')
        
        # 获取描述
        description = flow.get('description', '无描述')
        
        # 获取文件路径和Sheet名称
        file_path = flow.get('file_path', '未知文件')
        sheet_name = flow.get('sheet_name', '未知Sheet')
        
        # 显示用例信息
        print(f"  {status_icon} [{i}/{negative_index}] {description}")
        print(f"      文件: {file_path}")
        print(f"      Sheet: {sheet_name}")
        print(f"      浏览器: {browser}")
        print()
    
    print("=== 用例列表结束 ===")
    input("按回车键继续...")

def show_main_menu():
    """显示主菜单"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
        print("=" * 60)
        print("                   自动化测试与Codegen工具")
        print("=" * 60)
        print()
        print("  请选择要执行的操作:")
        print()
        print("  测试执行模式:")
        print("    1. Function模式 (软断言，执行所有启用的流程)")
        print("    2. Session模式  (硬断言，执行指定启用的流程)")
        print("       示例: 2 1 (执行第一个流程), 2 -1 (执行最后一个流程)")
        print("    3. Session模式-Browsers (硬断言，指定流程在所有浏览器上执行)")
        print("       示例: 3 1 (第一个流程在所有浏览器上执行), 3 -1 (最后一个流程在所有浏览器上执行)")
        print("    4. Session模式-All (硬断言，执行所有启用的流程)")
        print("    5. Function模式-Sheets (软断言，执行指定Excel文件中的所有sheet)")
        print("       示例: 5 1 (执行第一个流程Excel文件中的所有sheet)")
        print("    6. Session模式-Sheets (硬断言，执行指定Excel文件中的所有sheet)")
        print("       示例: 6 1 (执行第一个流程Excel文件中的所有sheet)")
        print()
        print("  Codegen2Excel工具:")
        print("    7. 从现有Python文件转换")
        print("    8. 启动Playwright录制并转换")
        print()
        print("  其他工具:")
        print("    9. test_config.json用例快速查看")
        print("    10. 清理残留临时文件")
        print()
        print("-" * 60)
        print("  q. 退出")
        print("-" * 60)
        print()
        
        choice_input = input("请输入您的选择 [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, q]: ").strip().lower()
        
        if not choice_input:
            print("无效输入，请重试...")
            input("按回车键继续...")
            continue
            
        # 解析选择输入
        parts = choice_input.split()
        if len(parts) == 1:
            choice, index = parts[0], None
        elif len(parts) == 2:
            choice, index = parts[0], parts[1]
        else:
            print("输入格式不正确，请重试...")
            input("按回车键继续...")
            continue
            
        if choice in ["1", "2", "3", "4", "5", "6"]:
            # 测试执行模式
            if index:
                run_tests(f"{choice} {index}", ci_mode=False)
            else:
                run_tests(choice, ci_mode=False)
                
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "7":
            # Codegen: 从现有Python文件转换
            convert_from_file()
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "8":
            # Codegen: 启动Playwright录制并转换
            record_and_convert()
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "9":
            # test_config.json用例快速查看
            view_test_cases()
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "10":
            # 清理残留临时文件
            from framework.utils.run_tests.runner import cleanup_temp_files
            cleanup_temp_files(ci_mode=False)
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice in ["q", "quit"]:
            print("退出脚本。")
            sys.exit(0)
        else:
            print("无效输入，请重试...")
            input("按回车键继续...")
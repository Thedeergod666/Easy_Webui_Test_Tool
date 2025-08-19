# framework/utils/ui/main_menu.py
import os
import sys

# 将项目根目录添加到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.run_tests.runner import run_tests
from framework.utils.ui.codegen_ui import convert_from_file, record_and_convert

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
        print()
        print("  Codegen2Excel工具:")
        print("    5. 从现有Python文件转换")
        print("    6. 启动Playwright录制并转换")
        print()
        print("  其他工具:")
        print("    7. 清理残留临时文件")
        print()
        print("-" * 60)
        print("  q. 退出")
        print("-" * 60)
        print()
        
        choice_input = input("请输入您的选择 [1, 2, 3, 4, 5, 6, 7, q]: ").strip().lower()
        
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
            
        if choice in ["1", "2", "3", "4"]:
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
        elif choice == "5":
            # Codegen: 从现有Python文件转换
            convert_from_file()
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "6":
            # Codegen: 启动Playwright录制并转换
            record_and_convert()
            
            # 执行完功能后询问是否返回主菜单
            print("\n功能执行完成。")
            cont = input("是否返回主菜单？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        elif choice == "7":
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
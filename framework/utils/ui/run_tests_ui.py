# framework/utils/ui/run_tests_ui.py
import os
import sys

# 将项目根目录添加到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.run_tests.runner import run_tests

def show_menu():
    """显示交互式菜单"""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')  # 清屏
        print("=================================================================")
        print()
        print("                   自动化测试执行菜单")
        print()
        print("-----------------------------------------------------------------")
        print()
        print("  请选择要执行的测试模式:")
        print()
        print("     1. Function模式 (软断言，执行所有启用的流程)")
        print()
        print("     2. Session模式  (硬断言，执行指定启用的流程)")
        print("        示例: 2 1 (执行第一个流程), 2 -1 (执行最后一个流程)")
        print()
        print("     3. Session模式-Browsers (硬断言，指定流程在所有浏览器上执行)")
        print("        示例: 3 1 (第一个流程在所有浏览器上执行), 3 -1 (最后一个流程在所有浏览器上执行)")
        print()
        print("     4. Session模式-All (硬断言，执行所有启用的流程)")
        print()
        print("     q. 退出")
        print()
        print("-----------------------------------------------------------------")
        
        choice_input = input("请输入您的选择 [1, 2, 3, 4, q]: ").strip().lower()
        
        if not choice_input:
            print("无效输入，请重试...")
            input("按回车键继续...")
            continue
            
        choice = choice_input.split()[0]
        if choice in ["1", "2", "3", "4"]:
            return choice_input
        elif choice in ["q", "quit"]:
            print("退出脚本。")
            sys.exit(0)
        else:
            print("无效输入，请重试...")
            input("按回车键继续...")

def run_with_menu():
    """运行测试执行菜单"""
    while True:
        choice_input = show_menu()
        choice = choice_input.split()[0] if choice_input else None
        if choice in ["1", "2", "3", "4"]:
            print(f"[交互模式] 选择模式: {choice}")
            run_tests(choice_input, ci_mode=False)
            
            # 交互模式下执行完一次后询问是否继续
            print("\n测试执行完成。")
            cont = input("是否继续执行其他测试？(y/回车继续，其他输入退出): ").strip().lower()
            if cont not in ["y", "Y", "yes", "是", ""]:  # 添加空字符串表示回车继续
                print("退出脚本。")
                break
        else:
            print(f"[交互模式] 无效的模式: {choice}")
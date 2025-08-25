# framework/utils/main.py
import sys
import os

# 将项目根目录添加到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.ui.main_menu import show_main_menu
from framework.utils.run_tests.runner import run_tests, cleanup_temp_files

def main():
    """主函数"""
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        # 非交互模式
        mode_args = sys.argv[1:]  # 获取所有参数
        choice_input = " ".join(mode_args)  # 将参数连接成字符串
        print(f"[非交互模式] 执行: {choice_input}")
        
        # 检查是否是清理命令
        if mode_args[0] == "8":
            cleanup_temp_files(ci_mode=True)
        # 检查是否是用例查看命令
        elif mode_args[0] == "7":
            from framework.utils.ui.main_menu import view_test_cases
            view_test_cases()
        # 检查是否是Codegen命令
        elif mode_args[0] == "5":
            # 从现有Python文件转换
            if len(mode_args) >= 3:
                py_file = mode_args[1]
                flow_name = mode_args[2]
                # 如果flow_name包含路径分隔符，只取文件名部分
                if "/" in flow_name or "\\" in flow_name:
                    flow_name = os.path.splitext(os.path.basename(flow_name))[0]
                
                # 构建命令
                cmd = [
                    sys.executable, "-m", "framework.utils.codegen_to_excel.codegen_to_excel",
                    py_file, flow_name
                ]
                # 添加其他可选参数
                if "--sheet-name" in mode_args:
                    idx = mode_args.index("--sheet-name")
                    if idx + 1 < len(mode_args):
                        cmd.extend(["--sheet-name", mode_args[idx + 1]])
                if "--browser" in mode_args:
                    idx = mode_args.index("--browser")
                    if idx + 1 < len(mode_args):
                        cmd.extend(["--browser", mode_args[idx + 1]])
                if "--disabled" in mode_args:
                    cmd.append("--disabled")
                # 执行转换
                print(f"\n开始转换...")
                os.system(" ".join(cmd))
            else:
                print("[错误] Codegen命令需要至少2个参数: Python文件路径和流程名称")
        elif mode_args[0] == "6":
            # 启动Playwright录制并转换
            if len(mode_args) >= 2:
                flow_name = mode_args[1]
                # 如果flow_name包含路径分隔符，只取文件名部分
                if "/" in flow_name or "\\" in flow_name:
                    flow_name = os.path.splitext(os.path.basename(flow_name))[0]
                
                # 构建命令
                cmd = [
                    sys.executable, "-m", "framework.utils.codegen_to_excel.record_and_convert",
                    flow_name
                ]
                # 添加其他可选参数
                if "--sheet-name" in mode_args:
                    idx = mode_args.index("--sheet-name")
                    if idx + 1 < len(mode_args):
                        cmd.extend(["--sheet-name", mode_args[idx + 1]])
                if "--browser" in mode_args:
                    idx = mode_args.index("--browser")
                    if idx + 1 < len(mode_args):
                        cmd.extend(["--browser", mode_args[idx + 1]])
                if "--disabled" in mode_args:
                    cmd.append("--disabled")
                # 执行录制和转换
                print(f"\n开始录制和转换...")
                os.system(" ".join(cmd))
            else:
                print("[错误] Codegen录制命令需要至少1个参数: 流程名称")
        else:
            run_tests(choice_input, ci_mode=True)
    else:
        # 交互模式
        show_main_menu()

if __name__ == "__main__":
    main()
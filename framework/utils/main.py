# framework/utils/main.py
import sys
import os

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.ui.main_menu import show_main_menu
from framework.utils.executor import FunctionExecutor
from framework.utils.config_workflow import initialize_test_config

def ensure_test_config_exists():
    """
    确保test_config.json文件存在，如果不存在则创建默认配置
    """
    return initialize_test_config(project_root)

def show_help():
    """显示帮助信息"""
    help_text = """
使用方法:
  main.bat/main.sh [选项] [参数...]
  
选项:
  -h, --help    显示帮助信息
  init / 11     初始化或修复 test_data/test_config.json
  validate / 12 校验 test_data/test_config.json 与引用的 Excel
  
功能列表:
  1             Function模式 (软断言，执行所有启用的流程)
  2 INDEX       Session模式，执行指定启用的流程
  3 INDEX       Session模式-Browsers，指定流程在所有浏览器上执行
  4             Session模式-All (硬断言，执行所有启用的流程)
  5 INDEX       Function模式-Sheets，执行指定Excel文件中的所有sheet
  6 INDEX       Session模式-Sheets，执行指定Excel文件中的所有sheet
  7             从现有Python文件转换为Excel
  8             启动Playwright录制并转换为Excel
  9             查看test_config.json中的测试用例
  10            清理残留临时文件
  11            初始化或修复 test_config.json
  12            校验 test_config.json 与 Excel 引用

命令示例:
  # 测试执行模式
  main.bat/main.sh 1                    # Function模式
  main.bat/main.sh 2 1                  # Session模式，执行第一个流程
  main.bat/main.sh 3 -1                 # Session模式-Browsers，执行最后一个流程
  main.bat/main.sh 4                    # Session模式-All
  main.bat/main.sh 5 2                  # Function模式-Sheets，执行第二个流程的sheet
  main.bat/main.sh 6 3                  # Session模式-Sheets，执行第三个流程的sheet

  # Codegen工具
  main.bat/main.sh 7 --py-file path/to/file.py --flow-name flow_name --sheet-name Sheet1 --browser chromium
  main.bat/main.sh 8 --flow-name flow_name --sheet-name Sheet1 --browser chromium

  # 其他工具
  main.bat/main.sh 9                    # 查看用例
  main.bat/main.sh 10                   # 清理临时文件
  main.bat/main.sh init                 # 初始化或修复默认配置
  main.bat/main.sh validate             # 校验配置
"""
    print(help_text)

def main(argv=None):
    """主函数"""
    argv = list(sys.argv[1:] if argv is None else argv)

    # 检查是否有命令行参数
    if argv:
        # 检查是否是帮助参数
        if argv[0] in ['-h', '--help', 'help']:
            show_help()
            return 0

        # CICD模式
        mode_args = argv  # 获取所有参数
        print(f"[CICD模式] 执行: {' '.join(mode_args)}")

        # 解析命令行参数
        func_id, args = FunctionExecutor.parse_command_args(mode_args)

        if func_id is None:
            print("[错误] 未提供功能ID")
            return 1

        # 执行功能
        return FunctionExecutor.execute_function(func_id, args, ci_mode=True)

    # 交互模式在进入菜单前确保配置存在
    ensure_test_config_exists()
    show_main_menu()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

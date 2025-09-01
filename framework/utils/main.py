# framework/utils/main.py
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from framework.utils.ui.main_menu import show_main_menu
from framework.utils.executor import FunctionExecutor

def ensure_test_config_exists():
    """
    确保test_config.json文件存在，如果不存在则创建默认配置
    """
    # 获取项目根目录下的test_data路径
    test_data_dir = Path(project_root) / "test_data"
    config_file = test_data_dir / "test_config.json"
    
    # 默认配置内容
    default_config = {
        "visual_mode": {
            "headed": True,
            "slow_mo": 50
        },
        "test_flows": [
            {
                "file_path": "test_data/sample_test.xlsx",
                "sheet_name": "Sheet1",
                "description": "示例测试流程（请根据实际需求修改）",
                "browser": "chromium",
                "enabled": False
            }
        ]
    }
    
    try:
        # 如果配置文件已存在
        if config_file.exists():
            # 尝试读取并验证JSON格式
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    json.load(f)
                # 格式正确，不显示任何信息
                return
            except json.JSONDecodeError:
                # JSON格式错误，备份原文件
                backup_file = config_file.with_suffix('.json.backup')
                try:
                    config_file.rename(backup_file)
                    print("[警告] 原配置文件格式错误，已备份为test_config.json.backup并创建新配置")
                except Exception as e:
                    print(f"[警告] 备份原文件失败: {e}")
                    return
        
        # 创建test_data目录（如果不存在）
        test_data_dir.mkdir(parents=True, exist_ok=True)
        
        # 创建配置文件
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump(default_config, f, ensure_ascii=False, indent=4)
        
        print("[成功] 已自动创建默认配置文件: test_data/test_config.json")
        
    except PermissionError:
        print(f"[错误] 无法创建配置文件，权限不足: {config_file}")
    except Exception as e:
        print(f"[错误] 创建配置文件时发生错误: {e}")

def show_help():
    """显示帮助信息"""
    help_text = """
使用方法:
  main.bat/main.sh [选项] [参数...]
  
选项:
  -h, --help    显示帮助信息
  
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
"""
    print(help_text)

def main():
    """主函数"""
    # 确保test_config.json文件存在
    ensure_test_config_exists()
    
    # 检查是否有命令行参数
    if len(sys.argv) > 1:
        # 检查是否是帮助参数
        if sys.argv[1] in ['-h', '--help']:
            show_help()
            return
            
        # CICD模式
        mode_args = sys.argv[1:]  # 获取所有参数
        print(f"[CICD模式] 执行: {' '.join(mode_args)}")
        
        # 解析命令行参数
        func_id, args = FunctionExecutor.parse_command_args(mode_args)
        
        if func_id is None:
            print("[错误] 未提供功能ID")
            return
            
        # 执行功能
        FunctionExecutor.execute_function(func_id, args, ci_mode=True)
    else:
        # 交互模式
        show_main_menu()

if __name__ == "__main__":
    main()
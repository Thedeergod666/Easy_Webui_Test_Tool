# framework/utils/ui/view_test_cases.py
import os
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
        status_icon = "[v]" if flow.get('enabled', True) else "[x]"
        
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
    # 在CICD模式下不等待用户输入
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "ci":
        pass  # CICD模式下不等待用户输入
    else:
        input("按回车键继续...")

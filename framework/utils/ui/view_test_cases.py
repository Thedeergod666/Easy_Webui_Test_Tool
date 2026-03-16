# framework/utils/ui/view_test_cases.py
from framework.utils.config_workflow import load_test_config

def view_test_cases(non_interactive=False):
    """查看test_config.json中的测试用例"""
    result = load_test_config()
    if result.errors:
        for error in result.errors:
            print(f"[错误] {error}")
        if not non_interactive:
            input("按回车键继续...")
        return 1

    config = result.data or {}
    
    test_flows = config.get('test_flows', [])
    if not test_flows:
        print("[信息] 配置文件中没有找到测试用例")
        if not non_interactive:
            input("按回车键继续...")
        return 0
    
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
    if not non_interactive:
        input("按回车键继续...")
    return 0

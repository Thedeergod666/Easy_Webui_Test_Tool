# framework/utils/run_tests/runner.py
import json
import os
import sys
import subprocess
from datetime import datetime
from collections import defaultdict

# 添加项目根目录到sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 浏览器别名映射
BROWSER_ALIASES = {
    "cr": "chromium",
    "ff": "firefox",
    "wk": "webkit",
    "chromium": "chromium",
    "firefox": "firefox",
    "webkit": "webkit"
}

def get_test_flows():
    """从 test_config.json 加载并过滤启用的测试流程。"""
    config_path = os.path.join(project_root, 'test_data', 'test_config.json')
    if not os.path.exists(config_path):
        print(f"[错误] 配置文件不存在: {config_path}")
        return []
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    all_flows = config.get("test_flows", [])
    # 为没有指定浏览器的流程设置默认浏览器为chromium
    for flow in all_flows:
        if "browser" not in flow:
            flow["browser"] = "chromium"
    return [flow for flow in all_flows if flow.get("enabled", True)]

def group_flows_by_browser(flows):
    """根据浏览器对测试流程进行分组。"""
    grouped = defaultdict(list)
    for flow in flows:
        # 获取浏览器，默认为 chromium
        browser_key = flow.get("browser", "chromium").lower()
        # 解析别名
        browser_name = BROWSER_ALIASES.get(browser_key, "chromium")
        grouped[browser_name].append(flow)
    return grouped

def run_pytest_batch(browser, flows_for_browser, test_file_path, ci_mode=False):
    """为单个浏览器执行一批测试。"""
    print(f"\n{'='*20} 准备执行 {browser.upper()} 批次测试 {'='*20}")
    
    # 1. 创建一个临时的JSON文件，只包含当前浏览器的流程
    temp_config_path = os.path.join(project_root, 'test_data', f'temp_run_{browser}.json')
    with open(temp_config_path, 'w', encoding='utf-8') as f:
        json.dump(flows_for_browser, f, indent=4)
        
    # 2. 构造报告文件名和路径
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    date_str = datetime.now().strftime("%Y-%m-%d")
    ci_suffix = "_CI" if ci_mode else ""
    
    # 创建按日期分类的报告目录
    report_date_dir = os.path.join(project_root, 'reports', f'reports_{date_str}')
    if not os.path.exists(report_date_dir):
        os.makedirs(report_date_dir)
    
    # 报告名包含浏览器和状态，调整格式为: report_2025-07-30_17-30-55_firefox_CI_Failed.html
    report_filename = f"report_{timestamp}_{browser}{ci_suffix}.html"
    report_path = os.path.join(report_date_dir, report_filename)
    
    # 3. 构建pytest命令
    command = [
        sys.executable,  # 使用当前虚拟环境的python
        "-m", "pytest",
        "-s", "-v",
        "--browser", browser,
        "--html", report_path,
        "--self-contained-html",
        # 传递临时配置文件路径给测试文件
        f"--flow-config-file={temp_config_path}",
        test_file_path
    ]
    
    print(f"执行命令: {' '.join(command)}")
    
    # 4. 执行命令
    result = subprocess.run(command)
    
    # 5. 清理临时文件
    os.remove(temp_config_path)
    
    # 6. 重命名报告文件，添加成功/失败状态
    if result.returncode != 0:
        print(f"!!!!!! {browser.upper()} 批次测试执行失败 !!!!!!")
        failed_report_path = report_path.replace('.html', '_Failed.html')
        if os.path.exists(report_path):
            os.rename(report_path, failed_report_path)
            print(f"报告已生成: {failed_report_path}")
        return False
    else:
        print(f"====== {browser.upper()} 批次测试执行成功 ======")
        passed_report_path = report_path.replace('.html', '_Passed.html')
        if os.path.exists(report_path):
            os.rename(report_path, passed_report_path)
            print(f"报告已生成: {passed_report_path}")
        return True

def get_flow_by_index(test_flows, index):
    """根据索引获取测试流程"""
    if index is None:
        # 默认返回第一个流程
        return test_flows[0] if test_flows else None
    elif index > 0:
        # 正数索引，从1开始
        if 1 <= index <= len(test_flows):
            return test_flows[index - 1]
        else:
            print(f"索引 {index} 超出范围，将使用第一个流程")
            return test_flows[0] if test_flows else None
    else:
        # 负数索引，-1表示最后一个
        if -len(test_flows) <= index <= -1:
            return test_flows[len(test_flows) + index]
        else:
            print(f"索引 {index} 超出范围，将使用第一个流程")
            return test_flows[0] if test_flows else None

def run_tests(choice_input, ci_mode=False):
    """执行测试"""
    # 解析选择输入
    parts = choice_input.split()
    if len(parts) == 1:
        choice, flow_index = parts[0], None
    elif len(parts) == 2:
        choice = parts[0]
        try:
            flow_index = int(parts[1])
        except ValueError:
            print(f"无效的索引参数: {parts[1]}，将使用默认值")
            flow_index = None
    else:
        print(f"输入格式不正确，将使用默认值")
        choice, flow_index = choice_input, None
    
    test_flows = get_test_flows()
    if not test_flows:
        print("未找到任何启用的测试流程。")
        return
    
    if choice == "1":  # Function模式
        grouped_flows = group_flows_by_browser(test_flows)
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_flow_by_function_json.py')
        for browser, flows in grouped_flows.items():
            run_pytest_batch(browser, flows, test_file_py, ci_mode=ci_mode)
    
    elif choice == "2":  # Session模式
        # Session模式只跑指定索引的流程的第一个浏览器
        selected_flow = get_flow_by_index(test_flows, flow_index)
        if selected_flow is None:
            print("未找到指定的测试流程。")
            return
            
        browser = BROWSER_ALIASES.get(selected_flow.get("browser", "cr").lower(), "chromium")
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_steps_by_session_json.py')
        run_pytest_batch(browser, [selected_flow], test_file_py, ci_mode=ci_mode)
        
    elif choice == "3":  # Session模式-Browsers
        # Session模式在所有支持的浏览器上执行指定索引的流程
        selected_flow = get_flow_by_index(test_flows, flow_index)
        if selected_flow is None:
            print("未找到指定的测试流程。")
            return
            
        # 获取所有支持的浏览器
        supported_browsers = ["chromium", "firefox", "webkit"]
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_steps_by_session_json.py')
        for browser in supported_browsers:
            run_pytest_batch(browser, [selected_flow], test_file_py, ci_mode=ci_mode)
    
    elif choice == "4":  # Session模式-All
        # Session模式执行所有启用的流程
        grouped_flows = group_flows_by_browser(test_flows)
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_steps_by_session_json.py')
        for browser, flows in grouped_flows.items():
            run_pytest_batch(browser, flows, test_file_py, ci_mode=ci_mode)
            
    elif choice == "5":  # Function模式-Sheets
        # Function模式-Sheets执行指定Excel文件中的所有sheet
        selected_flow = get_flow_by_index(test_flows, flow_index)
        if selected_flow is None:
            print("未找到指定的测试流程。")
            return
            
        # 获取Excel文件路径
        excel_file_path = selected_flow.get("file_path")
        if not excel_file_path:
            print("指定的测试流程中没有配置Excel文件路径。")
            return
            
        # 处理相对路径
        if not os.path.isabs(excel_file_path):
            excel_file_path = os.path.join(project_root, excel_file_path)
            
        # 检查文件是否存在
        if not os.path.exists(excel_file_path):
            print(f"Excel文件不存在: {excel_file_path}")
            return
            
        # 获取Excel文件中的所有sheet名称
        import pandas as pd
        try:
            excel_file = pd.ExcelFile(excel_file_path)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            print(f"读取Excel文件失败: {e}")
            return
            
        # 为每个sheet创建测试流程配置
        sheet_flows = []
        for sheet_name in sheet_names:
            sheet_flow = selected_flow.copy()
            sheet_flow["sheet_name"] = sheet_name
            sheet_flow["description"] = f"{selected_flow.get('description', '未知流程')} - Sheet: {sheet_name}"
            sheet_flows.append(sheet_flow)
            
        # 按浏览器分组并执行
        grouped_flows = group_flows_by_browser(sheet_flows)
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_flow_by_function_json.py')
        for browser, flows in grouped_flows.items():
            run_pytest_batch(browser, flows, test_file_py, ci_mode=ci_mode)
            
    elif choice == "6":  # Session模式-Sheets
        # Session模式-Sheets执行指定Excel文件中的所有sheet
        selected_flow = get_flow_by_index(test_flows, flow_index)
        if selected_flow is None:
            print("未找到指定的测试流程。")
            return
            
        # 获取Excel文件路径
        excel_file_path = selected_flow.get("file_path")
        if not excel_file_path:
            print("指定的测试流程中没有配置Excel文件路径。")
            return
            
        # 处理相对路径
        if not os.path.isabs(excel_file_path):
            excel_file_path = os.path.join(project_root, excel_file_path)
            
        # 检查文件是否存在
        if not os.path.exists(excel_file_path):
            print(f"Excel文件不存在: {excel_file_path}")
            return
            
        # 获取Excel文件中的所有sheet名称
        import pandas as pd
        try:
            excel_file = pd.ExcelFile(excel_file_path)
            sheet_names = excel_file.sheet_names
        except Exception as e:
            print(f"读取Excel文件失败: {e}")
            return
            
        # 为每个sheet创建测试流程配置
        sheet_flows = []
        for sheet_name in sheet_names:
            sheet_flow = selected_flow.copy()
            sheet_flow["sheet_name"] = sheet_name
            sheet_flow["description"] = f"{selected_flow.get('description', '未知流程')} - Sheet: {sheet_name}"
            sheet_flows.append(sheet_flow)
            
        # 按浏览器分组并执行
        grouped_flows = group_flows_by_browser(sheet_flows)
        test_file_py = os.path.join(project_root, 'tests', 'test_flows', 'test_steps_by_session_json.py')
        for browser, flows in grouped_flows.items():
            run_pytest_batch(browser, flows, test_file_py, ci_mode=ci_mode)

def cleanup_temp_files(ci_mode=False):
    """清理残留的临时文件"""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
    test_data_dir = os.path.join(project_root, 'test_data')
    
    # 查找所有以temp_run_开头的临时文件
    temp_files = [f for f in os.listdir(test_data_dir) if f.startswith('temp_run_') and f.endswith('.json')]
    
    if not temp_files:
        print("未找到残留的临时文件。")
        return
    
    print(f"找到 {len(temp_files)} 个残留的临时文件:")
    for temp_file in temp_files:
        print(f"  - {temp_file}")
    
    # 在CI/CD模式下自动执行清理，否则询问用户确认
    if ci_mode:
        print("\nCI/CD模式下自动执行清理操作...")
        confirm = "y"
    else:
        # 询问用户是否确认删除
        confirm = input("\n是否确认删除这些临时文件？(y/N): ").strip().lower()
    
    if confirm in ["y", "yes", "是"]:
        for temp_file in temp_files:
            temp_file_path = os.path.join(test_data_dir, temp_file)
            try:
                os.remove(temp_file_path)
                print(f"已删除: {temp_file}")
            except Exception as e:
                print(f"删除 {temp_file} 失败: {e}")
        print("临时文件清理完成。")
    else:
        print("取消清理操作。")
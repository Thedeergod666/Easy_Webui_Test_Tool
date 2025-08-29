# tests/test_flows/test_steps_by_session.py (V2 - JSON配置驱动版)
import pandas as pd
import pytest
import os
import json # 1. 导入json模块
import sys

def load_test_data_from_config(config_file=None):
    """从配置文件加载测试流程配置。
    
    Args:
        config_file: 配置文件路径，如果提供则从该文件加载，否则从默认的test_config.json加载
    """
    # 构造配置文件的绝对路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    if config_file and os.path.exists(config_file):
        config_path = config_file
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                # 如果是临时配置文件，直接加载内容
                flows = json.load(f)
            # 对于临时配置文件，返回所有流程，因为用户明确选择了这些流程
            # 即使enabled=false也应该执行用户选择的流程
            return flows if isinstance(flows, list) else []
        except Exception as e:
            print(f"加载临时配置文件出错: {e}")
            return []
    else:
        config_path = os.path.join(project_root, 'test_data', 'test_config.json')
        if not os.path.exists(config_path):
            print(f"测试配置文件不存在: {config_path}")
            return []
        
        with open(config_path, 'r', encoding='utf-8') as f:
            # 如果是默认配置文件，获取test_flows列表
            config = json.load(f)
            flows = config.get("test_flows", [])
        
        # 只返回启用的测试流程（如果enabled键不存在，默认为True）
        # 为没有指定浏览器的流程设置默认浏览器为chromium
        for flow in flows:
            if "browser" not in flow:
                flow["browser"] = "chromium"
        enabled_flows = [flow for flow in flows if isinstance(flow, dict) and flow.get("enabled", True)]
        return enabled_flows

def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--flow-config-file",
        action="store",
        help="指定测试流程配置文件路径"
    )

def pytest_configure(config):
    """pytest配置初始化"""
    pass

def pytest_generate_tests(metafunc):
    """动态生成测试参数"""
    global all_steps  # 将global声明移到函数开始
    
    if "flow_config" in metafunc.fixturenames:
        # 获取配置文件路径
        config_file = metafunc.config.getoption("--flow-config-file", None)
        test_flows = load_test_data_from_config(config_file)
        metafunc.parametrize("flow_config", test_flows, scope="session")
    elif "test_step" in metafunc.fixturenames:
        # 检查是否有--flow-config-file参数
        config_file = metafunc.config.getoption("--flow-config-file", None)
        
        if config_file:
            # 如果提供了配置文件，则只从配置文件加载指定的流程
            flow_configs = load_test_data_from_config(config_file)
            all_steps = []
            for flow_config in flow_configs:
                excel_file = flow_config["file_path"]
                sheet_name = flow_config["sheet_name"]
                
                # 处理相对路径
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
                if not os.path.isabs(excel_file):
                    excel_path = os.path.join(project_root, excel_file)
                else:
                    excel_path = excel_file
                    
                if os.path.exists(excel_path):
                    steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')
                    all_steps.extend(steps)
                else:
                    print(f"警告: 测试文件不存在: {excel_path}")
            metafunc.parametrize('test_step', all_steps)
        else:
            # 默认行为：使用全局的all_steps，如果不存在则使用空列表
            if 'all_steps' in globals() and all_steps:
                metafunc.parametrize('test_step', all_steps)
            else:
                print("\n[警告] 未找到可用的测试步骤数据")
                metafunc.parametrize('test_step', [])

# 3. 在全局作用域加载数据
# 为了保持向后兼容性，如果没有通过命令行参数传递配置文件，则从默认配置加载
flows_to_run = load_test_data_from_config()
all_steps = [] # 默认为空列表

# 4. 只有在成功获取到配置时，才读取Excel
if flows_to_run:
    # 使用第一个启用的流程来读取步骤（保持向后兼容性）
    first_flow = flows_to_run[0]
    excel_path = first_flow.get("file_path")
    sheet_name = first_flow.get("sheet_name")
    
    if excel_path and sheet_name and os.path.exists(excel_path):
        print(f"\n[Session测试模式] 将从文件 '{excel_path}' (Sheet: '{sheet_name}') 加载所有测试步骤。")
        all_steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')
    else:
        print(f"\n[警告] Session测试模式配置的Excel文件不存在或配置不完整: {excel_path}")
else:
    print("\n[警告] Session测试模式未在 test_config.json 中找到任何启用的测试流程。")

# 逐个执行测试步骤的函数
def test_single_step(keywords_session, test_step): # <<<< 注意！这里用的是 keywords_session
    step_id = test_step.get('编号', '未知步骤')
    keyword = test_step.get('关键字')
    
    # 这里的逻辑可以简化，因为pytest会为每个失败的步骤单独生成报告
    execution_status = str(test_step.get('执行状态', '')).strip().lower()
    if execution_status == 'skip':
        pytest.skip(f"步骤 {step_id} 标记为跳过")

    if not keyword:
        pytest.skip(f"步骤 {step_id} 关键字为空")

    key_func = getattr(keywords_session, keyword, None)
    if not key_func:
        pytest.fail(f"关键字 '{keyword}' 不存在")
    
    print(f"\n🚀 ===> 执行步骤: {step_id} - {keyword} - {test_step.get('描述', '')}")
    key_func(**test_step) # 直接执行，如果失败，pytest会自动捕获并报告

if __name__ == '__main__':
    pytest.main(['-s', '-v', __file__])
    # pytest.main(['-s', '-v', '--headed', __file__])
    # 无视.json文件配置强制使用--headed有头模式，该功能已砍，如有强制参数需要请用pytest启动
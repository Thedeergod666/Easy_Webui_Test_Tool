# tests/test_flows/test_steps_by_session.py (V2 - JSON配置驱动版)
import pandas as pd
import pytest
import os
import json # 1. 导入json模块
import sys
from datetime import datetime

# 导入执行状态系统
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'framework'))
from utils.execution_status import (
    ExecutionStatus, StatusIcons, StatusMessages,
    format_status_message, is_try_status, is_skip_status, 
    is_end_status, is_normal_status, get_execution_status
)

def load_test_data_from_config(config_file=None):
    """从配置文件加载测试流程配置。
    
    Args:
        config_file: 配置文件路径，如果提供则从该文件加载，否则从默认的test_config.json加载
    """
    # 构造配置文件的绝对路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    
    if config_file and os.path.exists(config_file):
        config_path = config_file
        print(f"[调试] 使用临时配置文件: {config_path}")
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                # 如果是临时配置文件，直接加载内容
                flows = json.load(f)
            print(f"[调试] 从临时配置文件加载到 {len(flows)} 个流程")
            # 对于临时配置文件，返回所有流程，因为用户明确选择了这些流程
            # 即使enabled=false也应该执行用户选择的流程
            return flows if isinstance(flows, list) else []
        except Exception as e:
            print(f"加载临时配置文件出错: {e}")
            return []
    else:
        config_path = os.path.join(project_root, 'test_data', 'test_config.json')
        print(f"[调试] 使用默认配置文件: {config_path}")
        if not os.path.exists(config_path):
            print(f"测试配置文件不存在: {config_path}")
            return []
        
        with open(config_path, 'r', encoding='utf-8') as f:
            # 如果是默认配置文件，获取test_flows列表
            config = json.load(f)
            flows = config.get("test_flows", [])
        print(f"[调试] 从默认配置文件加载到 {len(flows)} 个流程")
        
        # 只返回启用的测试流程（如果enabled键不存在，默认为True）
        # 为没有指定浏览器的流程设置默认浏览器为chromium
        for flow in flows:
            if "browser" not in flow:
                flow["browser"] = "chromium"
        enabled_flows = [flow for flow in flows if isinstance(flow, dict) and flow.get("enabled", True)]
        print(f"[调试] 过滤后得到 {len(enabled_flows)} 个启用的流程")
        for i, flow in enumerate(enabled_flows):
            print(f"[调试] 启用的流程 {i+1}: {flow.get('file_path', 'N/A')} (Sheet: {flow.get('sheet_name', 'N/A')})")
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
            print(f"[调试] 从配置文件加载到 {len(flow_configs)} 个流程配置")
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
                    
                print(f"[调试] 尝试加载Excel文件: {excel_path} (Sheet: {sheet_name})")
                if os.path.exists(excel_path):
                    steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')
                    print(f"[调试] 从 {excel_path} 加载到 {len(steps)} 个测试步骤")
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
    print(f"[调试] Session模式下找到 {len(flows_to_run)} 个启用的流程")
    
    # 查找用户期望的测试流程（test_data/114514.xlsx, Sheet: 'Sheet1'）
    target_flow = None
    for flow in flows_to_run:
        # 标准化文件路径以进行比较
        flow_file_path = flow.get("file_path", "")
        flow_sheet_name = flow.get("sheet_name", "")
        
        # 检查是否匹配用户期望的流程
        if "114514.xlsx" in flow_file_path and flow_sheet_name == "Sheet1":
            target_flow = flow
            break
    
    # 如果找到了用户期望的流程，则使用该流程，否则使用第一个启用的流程
    if target_flow:
        selected_flow = target_flow
        print(f"[调试] 找到用户期望的测试流程: {selected_flow.get('file_path')} (Sheet: {selected_flow.get('sheet_name')})")
    else:
        selected_flow = flows_to_run[0]
        print(f"[调试] 未找到用户期望的测试流程，使用第一个启用的流程")
    
    excel_path = selected_flow.get("file_path")
    sheet_name = selected_flow.get("sheet_name")
    
    # 处理相对路径
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    if not os.path.isabs(excel_path):
        excel_path = os.path.join(project_root, excel_path)
    
    print(f"[调试] Session模式将使用流程: {excel_path} (Sheet: {sheet_name})")
    if excel_path and sheet_name and os.path.exists(excel_path):
        print(f"\n[Session测试模式] 将从文件 '{excel_path}' (Sheet: '{sheet_name}') 加载所有测试步骤。")
        all_steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')
        print(f"[调试] 从 {excel_path} 加载到 {len(all_steps)} 个测试步骤")
    else:
        print(f"\n[警告] Session测试模式配置的Excel文件不存在或配置不完整: {excel_path}")
else:
    print("\n[警告] Session测试模式未在 test_config.json 中找到任何启用的测试流程。")

# 逐个执行测试步骤的函数
def test_single_step(keywords_session, test_step, screenshots_dir_session):
    step_id = test_step.get('编号', '未知步骤')
    keyword = test_step.get('关键字')
    description = test_step.get('描述', '')
    
    execution_status = get_execution_status(test_step)
    
    # 处理跳过状态
    if is_skip_status(execution_status):
        pytest.skip(format_status_message(StatusIcons.SUCCESS, StatusMessages.SKIP, step_id))
    
    # 处理终止状态
    if is_end_status(execution_status):
        print(format_status_message(StatusIcons.END, StatusMessages.END, step_id))
        pytest.exit(f"测试流程在步骤 {step_id} 处终止")
    
    # 检查关键字是否存在
    if not keyword:
        if is_try_status(execution_status):
            print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, "关键字为空"))
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字为空")
        else:
            pytest.skip(f"步骤 {step_id} 关键字为空")

    key_func = getattr(keywords_session, keyword, None)
    if not key_func:
        if is_try_status(execution_status):
            print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, f"关键字 '{keyword}' 不存在"))
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字 '{keyword}' 不存在")
        else:
            pytest.fail(f"关键字 '{keyword}' 不存在")
    
    # 设置截图目录以支持try状态失败截图
    keywords_session.screenshots_dir = screenshots_dir_session
    
    # 执行关键字方法
    # 注意：try状态的处理现在在_log_action装饰器中实现
    print(f"\n🚀 ===> 执行步骤: {step_id} - {keyword} - {description}")
    
    # 直接调用关键字方法，让_log_action装饰器处理try状态的异常
    key_func(**test_step)
    
    # 如果执行到这里，说明步骤成功完成
    if is_try_status(execution_status):
        print(format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id))
    else:
        print(format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id))

if __name__ == '__main__':
    pytest.main(['-s', '-v', __file__])
    # pytest.main(['-s', '-v', '--headed', __file__])
    # 无视.json文件配置强制使用--headed有头模式，该功能已砍，如有强制参数需要请用pytest启动
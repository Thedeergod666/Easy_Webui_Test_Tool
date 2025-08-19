# tests/test_flows/test_service_system.py (最终软断言版)
import pandas as pd
import pytest
import os
import json
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
            # 只返回启用的测试流程（如果enabled键不存在，默认为True）
            enabled_flows = [flow for flow in flows if isinstance(flow, dict) and flow.get("enabled", True)]
            return enabled_flows
        except Exception as e:
            print(f"加载临时配置文件出错: {e}")
            return []
    else:
        config_path = os.path.join(project_root, 'test_data', 'test_config.json')
        if not os.path.exists(config_path):
            pytest.fail(f"测试配置文件不存在: {config_path}")
        
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
    if "flow_config" in metafunc.fixturenames:
        # 获取配置文件路径
        config_file = metafunc.config.getoption("--flow-config-file", None)
        test_flows = load_test_data_from_config(config_file)
        metafunc.parametrize("flow_config", test_flows)

# TEST_FLOWS = [
#     {
#         "file_path": r"E:\项目相关文档\电商-智能客服相关文档\电商-智能客服-UI测试用例表格.xlsx",
#         "sheet_name": "Sheet2",
#         "description": "智能客服业务冒烟流程测试" # 还可以加更多描述信息
#     },
#     # 如果有第二个流程，可以继续加
#     # {
#     #     "file_path": "支付流程.xlsx",
#     #     "sheet_name": "main_flow",
#     #     "description": "用户支付流程测试"
#     # },
# ]
 
def test_business_flow_soft_assert(keywords_func, flow_config):
    # 从配置字典中取出信息
    excel_file = flow_config["file_path"]
    sheet_name = flow_config["sheet_name"]
    flow_description = flow_config["description"]
 
    excel_path = flow_config["file_path"] # 绝对路径
    # 下列被注释的为相对路径，数据驱动测试用例放test_data文件夹下时用
    # excel_path = os.path.join(os.path.dirname(__file__), '..', '..', 'test_data', excel_file)
    if not os.path.exists(excel_path):
        pytest.fail(f"测试文件不存在: {excel_path}")
 
    # 打印时也可以用上描述信息，让日志更清晰
    print(f"\n\n{'='*20} 开始执行: {flow_description} {'='*20}")
 
    all_steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')
     
    # >> 核心：用于收集错误的列表 <<
    errors = []

    for index, test_step in enumerate(all_steps):
        step_id = test_step.get('编号', f'行号_{index+2}')
        description = test_step.get('描述', '无描述')
        keyword = test_step.get('关键字', '无关键字')
        
        print(f"\n───步骤 {step_id}: {description} ({keyword})───")

        execution_status = str(test_step.get('执行状态', '')).strip().lower()
        if execution_status == 'skip':
            print("✔️ 结果: [跳过]")
            continue
        
        if execution_status == 'end':
             print(f"🔚 在步骤 {step_id} 处标记为结束，终止流程。")
             break

        if not keyword or keyword == '无关键字':
            print("✔️ 结果: [跳过 - 缺少关键字]")
            continue

        key_func = getattr(keywords_func, keyword, None)
        if not key_func:
            error_message = f"步骤 '{step_id}: {description}' 失败: 关键字 '{keyword}' 不存在"
            print(f"❌ 结果: [失败] - 关键字 '{keyword}' 不存在")
            errors.append(error_message)
            continue # 继续下一个步骤
        
        try:
            key_func(**test_step)
            print("✔️ 结果: [通过]")
        except Exception as e:
            error_path = f"error_{step_id}.png"
            # >> 核心：记录错误，而不是抛出 <<
            error_message = f"步骤 '{step_id}: {description}' 失败: {e}"
            print(f"❌ 结果: [失败] - {e}")
            errors.append(error_message)
            
            try:
                # 修复截图功能，使用keywords_func的active_page属性
                keywords_func.active_page.screenshot(path=error_path, full_page=True)
                print(f"📷  截图已保存至: {error_path}")
            except Exception as se:
                print(f"📷  截图失败: {se}")
            
            # >> 核心：继续循环 <<
            continue 

    print(f"\n{'='*20} 业务流程 {excel_file} 执行完毕 {'='*20}")

    # >> 核心：在所有步骤执行完毕后，统一报告 <<
    if errors:
        all_errors_message = f"\n\n在流程 [{excel_file}] 中发现以下 {len(errors)} 个错误:\n\n" + "\n\n".join(f"[{i+1}] {err}" for i, err in enumerate(errors))
        pytest.fail(all_errors_message, pytrace=False)


if __name__ == '__main__':
    pytest.main(['-s', '-v', __file__])
    # pytest.main(['-s', '-v', '--headed', __file__]) 
    # 无视.json文件配置强制使用--headed有头模式，该功能已砍，如有强制参数需要请用pytest启动

# tests/test_flows/test_service_system.py (最终软断言版)
import pandas as pd
import pytest
import os
import sys
from datetime import datetime

# 导入执行状态系统
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'framework'))
from utils.execution_status import (
    ExecutionStatus, StatusIcons, StatusMessages,
    format_status_message, is_try_status, is_skip_status, 
    is_end_status, is_normal_status, get_execution_status
)

# 单独的function测试用例，可以放在test_flows里快速自定义，方便调试，
# 长期的用例放在test_data里，用test_flow_by_function_json.py来测试

TEST_FLOWS = [
    {
        "file_path": r"E:\项目相关文档\电商-智能客服相关文档\电商-智能客服-UI测试用例表格.xlsx",
        "sheet_name": "Sheet2",
        "description": "智能客服业务冒烟流程测试" # 还可以加更多描述信息
    },
    # 如果有第二个流程，可以继续加
    # {
    #     "file_path": "支付流程.xlsx",
    #     "sheet_name": "main_flow",
    #     "description": "用户支付流程测试"
    # },
]
 

@pytest.mark.parametrize('flow_config', TEST_FLOWS)
def test_business_flow_soft_assert(keywords_func, flow_config, screenshots_dir):
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

        execution_status = get_execution_status(test_step)
        
        # 处理跳过状态
        if is_skip_status(execution_status):
            print(format_status_message(StatusIcons.SUCCESS, StatusMessages.SKIP, step_id))
            continue
        
        # 处理终止状态
        if is_end_status(execution_status):
            print(format_status_message(StatusIcons.END, StatusMessages.END, step_id))
            print(f"测试流程在步骤 {step_id} 处终止")
            break
        
        # 处理尝试执行状态
        if is_try_status(execution_status):
            if not keyword or keyword == '无关键字':
                print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, "缺少关键字"))
                continue
            
            key_func = getattr(keywords_func, keyword, None)
            if not key_func:
                print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, f"关键字 '{keyword}' 不存在"))
                continue
            
            try:
                key_func(**test_step)
                print(format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id))
            except Exception as e:
                print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, str(e)))
                # 尝试截图但不影响流程
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
                    error_path = os.path.join(screenshots_dir, f"try_error_{step_id}_{timestamp}.png")
                    keywords_func.page.screenshot(path=error_path, full_page=True)
                    print(f"📷  尝试失败截图已保存至: {error_path}")
                except Exception as se:
                    print(f"📷  截图失败: {se}")
            continue
        
        # 处理正常执行状态

        if not keyword or keyword == '无关键字':
            print(format_status_message(StatusIcons.SUCCESS, StatusMessages.SKIP, step_id, "缺少关键字"))
            continue

        key_func = getattr(keywords_func, keyword, None)
        if not key_func:
            error_message = f"步骤 '{step_id}: {description}' 失败: 关键字 '{keyword}' 不存在"
            print(format_status_message(StatusIcons.FAILURE, StatusMessages.FAIL, step_id, f"关键字 '{keyword}' 不存在"))
            errors.append(error_message)
            continue # 继续下一个步骤
        
        try:
            key_func(**test_step)
            print(format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id))
        except Exception as e:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
            error_path = os.path.join(screenshots_dir, f"error_{step_id}_{timestamp}.png")
            # >> 核心：记录错误，而不是抛出 <<
            error_message = f"步骤 '{step_id}: {description}' 失败: {e}"
            print(format_status_message(StatusIcons.FAILURE, StatusMessages.FAIL, step_id, str(e)))
            errors.append(error_message)
            
            try:
                keywords_func.page.screenshot(path=error_path, full_page=True)
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
    pytest.main(['-s', '-v', '--headed', __file__])

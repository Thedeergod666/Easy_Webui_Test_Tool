# tests/test_flows/test_steps_by_session.py
import pandas as pd
import pytest
import os
import sys

# 导入执行状态系统
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'framework'))
from utils.execution_status import (
    ExecutionStatus, StatusIcons, StatusMessages,
    format_status_message, is_try_status, is_skip_status, 
    is_end_status, is_normal_status, get_execution_status
)

# 单独的session测试用例，可以在下面path、sheet里快速自定义，方便调试，
# 长期的用例放在test_data里，用test_steps_by_session_json.py来测试

# 读取Excel的逻辑要放在 parametrize 之前，所以放在全局
# excel_path = os.path.join(os.path.dirname(__file__), '..', '..', 'test_data', '电商-智能客服-UI测试用例表格.xlsx')
excel_path = r"E:\项目相关文档\电商-智能客服相关文档\电商-智能客服-UI测试用例表格.xlsx"
sheet_name = 'Sheet2'
all_steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna('').to_dict(orient='records')

@pytest.mark.parametrize('test_step', all_steps)
def test_single_step(keywords_session, test_step): # <<<< 注意！这里用的是 keywords_session
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
    
    # 处理尝试执行状态
    if is_try_status(execution_status):
        if not keyword:
            print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, "关键字为空"))
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字为空")
            return
            
        key_func = getattr(keywords_session, keyword, None)
        if not key_func:
            print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, f"关键字 '{keyword}' 不存在"))
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字 '{keyword}' 不存在")
            return
        
        try:
            print(f"\n🚀 ===> 尝试执行步骤: {step_id} - {keyword} - {description}")
            key_func(**test_step)
            print(format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id))
            return
        except Exception as e:
            print(format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, step_id, str(e)))
            # 尝试截图但不影响流程
            try:
                error_path = f"try_error_{step_id}.png"
                keywords_session.active_page.screenshot(path=error_path, full_page=True)
                print(f"📷  尝试失败截图已保存至: {error_path}")
            except Exception as se:
                print(f"📷  截图失败: {se}")
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过")
            return
    
    # 处理正常执行状态
    if not keyword:
        pytest.skip(f"步骤 {step_id} 关键字为空")

    key_func = getattr(keywords_session, keyword, None)
    if not key_func:
        pytest.fail(f"关键字 '{keyword}' 不存在")
    
    print(f"\n🚀 ===> 执行步骤: {step_id} - {keyword} - {description}")
    key_func(**test_step) # 直接执行，如果失败，pytest会自动捕获并报告
    print(format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id))


if __name__ == '__main__':
    pytest.main(['-s', '-v', '--headed', __file__])
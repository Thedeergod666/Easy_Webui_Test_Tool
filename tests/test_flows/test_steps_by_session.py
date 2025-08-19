# tests/test_flows/test_steps_by_session.py
import pandas as pd
import pytest
import os

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
    pytest.main(['-s', '-v', '--headed', __file__])
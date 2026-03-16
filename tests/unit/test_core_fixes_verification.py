# -*- coding: utf-8 -*-
"""
快速验证Try状态修复功能
"""

import pytest
import os
import sys

# 添加项目路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from framework.keywords.element_locator import ElementLocatorMixin
from framework.utils.execution_status import is_try_status, get_execution_status


def test_codegen_prefix_processing():
    """验证Codegen前缀处理功能"""
    locator_mixin = ElementLocatorMixin()
    
    # 测试错误前缀不会被静默修复
    with pytest.raises(ValueError, match="无效页面引用"):
        locator_mixin._process_codegen_prefix("page13.get_by_role('button', name='×')")
    
    # 测试正常代码不被影响
    result = locator_mixin._process_codegen_prefix("locator('#test')")
    assert result == "locator('#test')"
    
    print("[PASS] Codegen前缀处理功能正常")


def test_try_status_detection():
    """验证try状态检测功能"""
    assert is_try_status("try") == True
    assert is_try_status("TRY") == True
    assert is_try_status(" try ") == True
    assert is_try_status("normal") == False
    assert is_try_status("") == False
    
    # 测试从测试步骤中获取状态
    test_step = {"执行状态": "try", "关键字": "click"}
    assert get_execution_status(test_step) == "try"
    
    test_step = {"关键字": "click"}  # 没有执行状态
    assert get_execution_status(test_step) == ""
    
    print("✅ Try状态检测功能正常")


def test_status_format():
    """验证状态格式化功能"""
    from framework.utils.execution_status import (
        StatusIcons, StatusMessages, format_status_message
    )
    
    result = format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, "test_001")
    expected = "[PASS] 结果: [尝试成功] - 步骤 test_001"
    assert result == expected
    
    result = format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP, "test_002", "测试错误")
    expected = "[WARN] 结果: [尝试失败-已跳过] - 步骤 test_002 - 测试错误"
    assert result == expected
    
    print("[PASS] 状态格式化功能正常")


if __name__ == '__main__':
    test_codegen_prefix_processing()
    test_try_status_detection()
    test_status_format()
    print("\n[PASS] 所有核心功能验证通过！")

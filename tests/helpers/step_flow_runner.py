# -*- coding: utf-8 -*-
"""可复用的测试步骤执行辅助函数。"""

import os
from datetime import datetime

import pytest

from framework.utils.execution_status import (
    StatusIcons,
    StatusMessages,
    format_status_message,
    get_execution_status,
    is_end_status,
    is_skip_status,
    is_try_status,
)


def execute_test_step(keywords, test_step, screenshots_dir):
    """执行单个测试步骤，供 session 流和单元测试复用。"""
    step_id = test_step.get("编号", "未知步骤")
    keyword = test_step.get("关键字")
    description = test_step.get("描述", "")

    execution_status = get_execution_status(test_step)

    if is_skip_status(execution_status):
        pytest.skip(format_status_message(StatusIcons.SUCCESS, StatusMessages.SKIP, step_id))

    if is_end_status(execution_status):
        print(format_status_message(StatusIcons.END, StatusMessages.END, step_id))
        pytest.exit(f"测试流程在步骤 {step_id} 处终止")

    if not keyword:
        if is_try_status(execution_status):
            print(
                format_status_message(
                    StatusIcons.WARNING,
                    StatusMessages.TRY_FAIL_SKIP,
                    step_id,
                    "关键字为空",
                )
            )
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字为空")
        pytest.skip(f"步骤 {step_id} 关键字为空")

    key_func = getattr(keywords, keyword, None)
    if not key_func:
        if is_try_status(execution_status):
            print(
                format_status_message(
                    StatusIcons.WARNING,
                    StatusMessages.TRY_FAIL_SKIP,
                    step_id,
                    f"关键字 '{keyword}' 不存在",
                )
            )
            pytest.skip(f"步骤 {step_id} 尝试失败但已跳过 - 关键字 '{keyword}' 不存在")
        pytest.fail(f"关键字 '{keyword}' 不存在")

    keywords.screenshots_dir = screenshots_dir
    print(f"\n[STEP] ===> 执行步骤: {step_id} - {keyword} - {description}")
    try:
        key_func(**test_step)
    except Exception as error:
        if not is_try_status(execution_status):
            raise

        print(
            format_status_message(
                StatusIcons.WARNING,
                StatusMessages.TRY_FAIL_SKIP,
                step_id,
                str(error),
            )
        )
        if screenshots_dir and hasattr(keywords, "active_page"):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            error_path = os.path.join(screenshots_dir, f"try_error_{step_id}_{timestamp}.png")
            keywords.active_page.screenshot(path=error_path, full_page=True)
            if hasattr(keywords, "_integrate_screenshot_to_html_report"):
                keywords._integrate_screenshot_to_html_report(error_path, step_id)
        pytest.skip(f"步骤 {step_id} 尝试失败但已跳过")

    if is_try_status(execution_status):
        print(format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id))
    else:
        print(format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id))

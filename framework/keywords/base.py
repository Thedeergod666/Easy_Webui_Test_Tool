# -*- coding: utf-8 -*-
"""
基础模块
提供关键字框架的基础类和通用功能
"""

import os
import re
import pytest
import ast
import time
import functools
from datetime import datetime
from playwright.sync_api import Page, Locator, expect, Error as PlaywrightTimeoutError, BrowserContext

# 导入执行状态系统
try:
    from ..utils.execution_status import (
        ExecutionStatus, StatusIcons, StatusMessages,
        format_status_message, is_try_status, is_skip_status, 
        is_end_status, is_normal_status, get_execution_status
    )
except ImportError:
    # 向后兼容处理
    def is_try_status(status):
        return str(status).strip().lower() == "try"
    def get_execution_status(test_step):
        return str(test_step.get('执行状态', '')).strip().lower()

# 全局变量，用于在测试会话结束时报告总的sleep时间
_total_sleep_time = 0.0


def _log_action(func):
    """
    装饰器，用于自动记录关键字操作的详细步骤，包括截图和状态记录。
    支持try状态感知的异常处理，在try状态下不传播异常。
    
    :param func: 被装饰的函数
    :return: 装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 获取self实例
        self = args[0] if args else None
        if not self or not hasattr(self, 'report_logger') or not self.report_logger:
            # 如果没有report_logger，直接执行原函数
            return func(*args, **kwargs)
        
        # 提取关键字信息
        keyword_name = func.__name__
        description = kwargs.get('描述', keyword_name)
        target = kwargs.get('目标对象', '')
        locator_type = kwargs.get('定位方式', '')
        data_content = kwargs.get('数据内容', '')
        step_id = kwargs.get('编号', '未知步骤')
        
        # 检查执行状态
        execution_status = get_execution_status(kwargs)
        is_try_execution = is_try_status(execution_status)
        
        # 构建详细信息
        details = {}
        if target:
            details['target'] = target
        if locator_type:
            details['locator_type'] = locator_type
        if data_content:
            details['data_content'] = data_content
        if execution_status:
            details['execution_status'] = execution_status
        
        # 开始记录步骤
        self.report_logger.start_step(
            keyword=keyword_name,
            description=description,
            details=details
        )
        
        try:
            # 执行原函数
            result = func(*args, **kwargs)
            # 结束记录步骤（成功）
            if is_try_execution:
                self.report_logger.end_step(
                    'PASS',
                    format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id),
                )
            else:
                self.report_logger.end_step('PASS')
            return result
        except Exception as e:
            # 记录失败状态
            error_msg = f"{type(e).__name__}: {str(e)}"
            
            if is_try_execution:
                # try状态：捕获异常但不传播，生成截图并跳过
                try:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]  # 包含毫秒
                    screenshots_dir = getattr(self, 'screenshots_dir', None)
                    
                    if screenshots_dir and hasattr(self, 'active_page'):
                        error_path = os.path.join(screenshots_dir, f"try_error_{step_id}_{timestamp}.png")
                        self.active_page.screenshot(path=error_path, full_page=True)
                        print(f"[REPORT] try状态失败截图已保存至: {error_path}")
                        
                        # 将截图集成到HTML报告
                        self._integrate_screenshot_to_html_report(error_path, step_id)
                    else:
                        print("[REPORT] 无法生成try状态失败截图：缺少screenshots_dir或active_page")
                except Exception as se:
                    print(f"[REPORT] try状态截图失败: {se}")
                
                # 记录try状态失败但不传播异常
                warning_msg = format_status_message(
                    StatusIcons.WARNING,
                    StatusMessages.TRY_FAIL_SKIP,
                    step_id,
                    error_msg,
                )
                self.report_logger.end_step('SKIP', warning_msg)
                
                # 使用pytest.skip跳过而不是失败
                pytest.skip(warning_msg)
                return None  # 这行不会执行，但保持代码的可读性
            else:
                # 正常状态：记录失败并重新抛出异常
                self.report_logger.end_step('FAIL', error_msg)
                raise  # 重新抛出异常，不影响测试执行
            
    return wrapper



class Keywords:
    DEFAULT_TIMEOUT = 10000

    def __init__(self, page: Page, report_logger=None):
        """
        初始化Keywords实例。
        持有整个浏览器上下文(Context)以管理多个页面，并设置初始活动页面。
        """
        self.context: BrowserContext = page.context
        self.active_page: Page = page  # 初始活动页面是主页面
        self.report_logger = report_logger  # ReportLogger实例，用于记录测试步骤
        
        # 将默认超时应用到初始页面
        self.active_page.set_default_timeout(self.DEFAULT_TIMEOUT)
        
        # 从上下文中获取运行模式
        self.mode = getattr(self.context, 'running_mode', 'headed')
        self.expect = expect
        
        # 初始化页面生命周期管理器（在Mixin中实现）
        # 这里不直接初始化，由PageManagementMixin负责
        
        # 设置截图目录（按照项目规范：reports/reports_YYYY-MM-DD/screenshots/）
        self.screenshots_dir = getattr(self, 'screenshots_dir', None)
        if not self.screenshots_dir:
            # 默认截图目录使用日期格式
            today = datetime.now().strftime('%Y-%m-%d')
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
            self.screenshots_dir = os.path.join(project_root, 'reports', f'reports_{today}', 'screenshots')
            if not os.path.exists(self.screenshots_dir):
                os.makedirs(self.screenshots_dir, exist_ok=True)
    
    def _integrate_screenshot_to_html_report(self, screenshot_path: str, step_id: str):
        """
        [内部] 将截图集成到HTML报告中
        使用pytest-html插件的extras功能将截图以base64格式嵌入报告
        
        Args:
            screenshot_path: 截图文件路径
            step_id: 步骤ID
        """
        try:
            if not os.path.exists(screenshot_path):
                print(f"    [HTML报告集成] 截图文件不存在: {screenshot_path}")
                return
                
            # 将截图信息存储到全局变量中，供 pytest hook 使用
            if not hasattr(self, '_try_failure_screenshots'):
                self._try_failure_screenshots = []
            
            screenshot_info = {
                'path': screenshot_path,
                'step_id': step_id,
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            self._try_failure_screenshots.append(screenshot_info)
            
            print(f"    [HTML报告集成] Try失败截图已标记为待集成: {step_id}")
            
            # 尝试直接集成（如果在pytest上下文中）
            self._try_direct_integration(screenshot_path, step_id)
            
        except Exception as e:
            print(f"    [HTML报告集成] 集成失败: {e}")
    
    def _try_direct_integration(self, screenshot_path: str, step_id: str):
        """
        [内部] 尝试直接集成截图到HTML报告
        """
        try:
            import pytest_html.extras
            
            # 读取截图文件
            with open(screenshot_path, 'rb') as f:
                screenshot_data = f.read()
            
            # 直接添加到当前的pytest上下文
            pytest_html.extras.png(screenshot_data, name=f"Try失败截图 - 步骤 {step_id}")
            
            # 添加HTML描述信息
            html_info = f"""
            <div style="margin: 10px 0; padding: 10px; border-left: 4px solid #ff9800; background-color: #fff3cd;">
                <h4 style="margin: 0 0 5px 0; color: #856404;">Try状态失败截图</h4>
                <p style="margin: 0; color: #856404;">步骤ID: {step_id}</p>
                <p style="margin: 0; color: #856404;">截图时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p style="margin: 0; color: #856404;">文件路径: {screenshot_path}</p>
            </div>
            """
            pytest_html.extras.html(html_info)
            
            print("    [HTML报告集成] Try失败截图已集成到HTML报告")
            
        except ImportError:
            print(f"    [HTML报告集成] 未安装pytest-html插件，跳过直接集成")
        except Exception as e:
            print(f"    [HTML报告集成] 直接集成失败: {e}")

# -*- coding: utf-8 -*-
"""
Try状态错误处理单元测试
验证try状态处理缺陷的修复功能
"""

import pytest
import os
import tempfile
import sys
from unittest.mock import Mock, patch, MagicMock

# 添加项目路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from framework.keywords.element_locator import ElementLocatorMixin
from framework.keywords.base import Keywords, _log_action
from framework.utils.execution_status import (
    ExecutionStatus, StatusIcons, StatusMessages,
    format_status_message, is_try_status, get_execution_status
)
from playwright.sync_api import Page


class MockPage:
    """模拟Page对象用于测试"""
    
    def __init__(self):
        self.screenshot_called = False
        self.screenshot_path = None
        
    def screenshot(self, path=None, full_page=True):
        self.screenshot_called = True
        self.screenshot_path = path
        # 创建一个空的截图文件用于测试
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'fake_screenshot_data')
        return b'fake_screenshot_data'
    
    def locator(self, selector):
        return MockLocator()
    
    def get_by_role(self, role, **kwargs):
        return MockLocator()
    
    def get_by_text(self, text):
        return MockLocator()
    
    def set_default_timeout(self, timeout):
        """模拟设置默认超时"""
        self.default_timeout = timeout


class MockLocator:
    """模拟Locator对象用于测试"""
    
    def click(self):
        pass
    
    def fill(self, text):
        pass
    
    def first(self):
        return MockLocator()
    
    def count(self):
        return 1


class TestCodegenPrefixProcessing:
    """测试Codegen前缀处理功能"""
    
    def setup_method(self):
        """设置测试环境"""
        self.locator_mixin = ElementLocatorMixin()
        self.mock_page = MockPage()
    
    def test_process_codegen_prefix_with_error_prefix(self):
        """测试错误前缀的处理"""
        # 测试page13.前缀
        result = self.locator_mixin._process_codegen_prefix("page13.get_by_role('button', name='×')")
        assert result == "get_by_role('button', name='×')"
        
        # 测试page1.前缀
        result = self.locator_mixin._process_codegen_prefix("page1.locator('#submit')")
        assert result == "locator('#submit')"
        
        # 测试page999.前缀
        result = self.locator_mixin._process_codegen_prefix("page999.click()")
        assert result == "click()"
    
    def test_process_codegen_prefix_with_duplicate_prefix(self):
        """测试重复page.前缀的处理"""
        result = self.locator_mixin._process_codegen_prefix("page.locator('#test')")
        assert result == "locator('#test')"
        
        result = self.locator_mixin._process_codegen_prefix("page.get_by_text('Hello')")
        assert result == "get_by_text('Hello')"
    
    def test_process_codegen_prefix_with_normal_code(self):
        """测试正常代码的处理"""
        result = self.locator_mixin._process_codegen_prefix("locator('#normal')")
        assert result == "locator('#normal')"
        
        result = self.locator_mixin._process_codegen_prefix("get_by_role('button')")
        assert result == "get_by_role('button')"
    
    def test_process_codegen_prefix_with_empty_input(self):
        """测试空输入的处理"""
        result = self.locator_mixin._process_codegen_prefix("")
        assert result == ""
        
        result = self.locator_mixin._process_codegen_prefix(None)
        assert result is None
    
    @patch('builtins.print')
    def test_process_codegen_prefix_logging(self, mock_print):
        """测试前缀处理的日志输出"""
        self.locator_mixin._process_codegen_prefix("page13.get_by_role('button')")
        
        # 验证日志输出
        assert mock_print.call_count >= 2
        log_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Codegen智能修复" in log for log in log_calls)
        assert any("检测到错误前缀" in log for log in log_calls)


class TestTryStatusErrorHandling:
    """测试Try状态错误处理功能"""
    
    def setup_method(self):
        """设置测试环境"""
        self.mock_page = MockPage()
        self.mock_context = Mock()
        self.mock_context.pages = [self.mock_page]
        self.mock_page.context = self.mock_context
        
        self.mock_report_logger = Mock()
        self.mock_report_logger.start_step = Mock()
        self.mock_report_logger.end_step = Mock()
        
        self.keywords = Keywords(self.mock_page, self.mock_report_logger)
        self.keywords.screenshots_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        if hasattr(self, 'keywords') and self.keywords.screenshots_dir:
            shutil.rmtree(self.keywords.screenshots_dir, ignore_errors=True)
    
    def test_try_status_detection(self):
        """测试try状态检测"""
        assert is_try_status("try") == True
        assert is_try_status("TRY") == True
        assert is_try_status(" try ") == True
        assert is_try_status("normal") == False
        assert is_try_status("") == False
        assert is_try_status(None) == False
    
    def test_get_execution_status(self):
        """测试执行状态获取"""
        test_step = {"执行状态": "try", "关键字": "click"}
        assert get_execution_status(test_step) == "try"
        
        test_step = {"执行状态": "skip", "关键字": "click"}
        assert get_execution_status(test_step) == "skip"
        
        test_step = {"关键字": "click"}  # 没有执行状态
        assert get_execution_status(test_step) == ""
    
    @patch('pytest.skip')
    def test_log_action_decorator_with_try_status_success(self, mock_skip):
        """测试_log_action装饰器处理try状态成功情况"""
        
        @_log_action
        def mock_keyword_method(self, **kwargs):
            return "success"
        
        # 绑定方法到keywords实例
        mock_keyword_method.__get__(self.keywords, Keywords)
        
        test_step = {
            "执行状态": "try",
            "关键字": "mock_keyword",
            "编号": "test_001",
            "描述": "测试try状态成功"
        }
        
        result = mock_keyword_method(self.keywords, **test_step)
        
        # 验证成功执行
        assert result == "success"
        assert not mock_skip.called
        
        # 验证日志记录
        self.mock_report_logger.start_step.assert_called_once()
        self.mock_report_logger.end_step.assert_called_once()
        
        # 检查end_step调用参数
        end_step_args = self.mock_report_logger.end_step.call_args[0]
        assert end_step_args[0] == 'PASS'
        assert '[尝试成功]' in end_step_args[1]
    
    @patch('pytest.skip')
    @patch('os.path.exists')
    def test_log_action_decorator_with_try_status_failure(self, mock_exists, mock_skip):
        """测试_log_action装饰器处理try状态失败情况"""
        
        @_log_action
        def mock_failing_keyword_method(self, **kwargs):
            raise ValueError("模拟的try状态失败")
        
        # 绑定方法到keywords实例
        mock_failing_keyword_method.__get__(self.keywords, Keywords)
        
        test_step = {
            "执行状态": "try",
            "关键字": "mock_failing_keyword",
            "编号": "test_002",
            "描述": "测试try状态失败"
        }
        
        # 模拟截图文件存在
        mock_exists.return_value = True
        
        # 执行应该通过pytest.skip退出，不抛出异常
        mock_failing_keyword_method(self.keywords, **test_step)
        
        # 验证pytest.skip被调用
        assert mock_skip.called
        skip_message = mock_skip.call_args[0][0]
        assert '尝试失败-已跳过' in skip_message
        assert 'test_002' in skip_message
        
        # 验证截图被调用
        assert self.mock_page.screenshot_called
        assert self.mock_page.screenshot_path is not None
        assert 'try_error_test_002_' in self.mock_page.screenshot_path
        
        # 验证日志记录
        self.mock_report_logger.start_step.assert_called_once()
        self.mock_report_logger.end_step.assert_called_once()
        
        # 检查end_step调用参数
        end_step_args = self.mock_report_logger.end_step.call_args[0]
        assert end_step_args[0] == 'SKIP'
        assert '[尝试失败-已跳过]' in end_step_args[1]
    
    @patch('pytest.skip')
    def test_log_action_decorator_with_normal_status_failure(self, mock_skip):
        """测试_log_action装饰器处理正常状态失败情况"""
        
        @_log_action
        def mock_failing_keyword_method(self, **kwargs):
            raise ValueError("模拟的正常状态失败")
        
        # 绑定方法到keywords实例
        mock_failing_keyword_method.__get__(self.keywords, Keywords)
        
        test_step = {
            "执行状态": "",  # 正常状态
            "关键字": "mock_failing_keyword",
            "编号": "test_003",
            "描述": "测试正常状态失败"
        }
        
        # 执行应该抛出异常
        with pytest.raises(ValueError, match="模拟的正常状态失败"):
            mock_failing_keyword_method(self.keywords, **test_step)
        
        # 验证pytest.skip没有被调用
        assert not mock_skip.called
        
        # 验证日志记录
        self.mock_report_logger.start_step.assert_called_once()
        self.mock_report_logger.end_step.assert_called_once()
        
        # 检查end_step调用参数
        end_step_args = self.mock_report_logger.end_step.call_args[0]
        assert end_step_args[0] == 'FAIL'
        assert 'ValueError: 模拟的正常状态失败' in end_step_args[1]


class TestHTMLReportIntegration:
    """测试HTML报告集成功能"""
    
    def setup_method(self):
        """设置测试环境"""
        self.mock_page = MockPage()
        self.mock_context = Mock()
        self.mock_context.pages = [self.mock_page]
        self.mock_page.context = self.mock_context
        
        self.keywords = Keywords(self.mock_page)
        self.keywords.screenshots_dir = tempfile.mkdtemp()
        
        # 创建测试截图文件
        self.test_screenshot_path = os.path.join(self.keywords.screenshots_dir, "test_screenshot.png")
        with open(self.test_screenshot_path, 'wb') as f:
            f.write(b'test_screenshot_data')
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        if hasattr(self, 'keywords') and self.keywords.screenshots_dir:
            shutil.rmtree(self.keywords.screenshots_dir, ignore_errors=True)
    
    @patch('builtins.print')
    def test_integrate_screenshot_to_html_report_no_pytest_html(self, mock_print):
        """测试没有pytest-html插件时的处理"""
        with patch.dict('sys.modules', {'pytest_html': None}):
            self.keywords._integrate_screenshot_to_html_report(self.test_screenshot_path, "test_001")
        
        # 验证输出了未安装插件的消息
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("未安装pytest-html插件" in msg for msg in print_calls)
    
    @patch('pytest_html.extras.png')
    @patch('pytest_html.extras.html')
    @patch('builtins.print')
    def test_integrate_screenshot_to_html_report_success(self, mock_print, mock_html, mock_png):
        """测试成功集成截图到HTML报告"""
        # 模拟pytest_html模块
        with patch.dict('sys.modules', {'pytest_html': Mock(), 'pytest_html.extras': Mock()}):
            import pytest_html
            pytest_html.extras.png = mock_png
            pytest_html.extras.html = mock_html
            
            self.keywords._integrate_screenshot_to_html_report(self.test_screenshot_path, "test_001")
        
        # 验证调用了pytest_html.extras.png
        mock_png.assert_called_once()
        png_call_args = mock_png.call_args
        assert b'test_screenshot_data' == png_call_args[0][0]
        assert "Try失败截图 - 步骤 test_001" == png_call_args[1]['name']
        
        # 验证调用了pytest_html.extras.html
        mock_html.assert_called_once()
        html_content = mock_html.call_args[0][0]
        assert "Try状态失败截图" in html_content
        assert "test_001" in html_content
        
        # 验证输出了成功消息
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("Try失败截图已集成到HTML报告" in msg for msg in print_calls)
    
    @patch('builtins.print')
    def test_integrate_screenshot_to_html_report_file_not_exists(self, mock_print):
        """测试截图文件不存在时的处理"""
        non_existent_path = os.path.join(self.keywords.screenshots_dir, "non_existent.png")
        
        # 模拟pytest_html模块
        with patch.dict('sys.modules', {'pytest_html': Mock(), 'pytest_html.extras': Mock()}):
            self.keywords._integrate_screenshot_to_html_report(non_existent_path, "test_001")
        
        # 验证输出了文件不存在的消息
        print_calls = [call.args[0] for call in mock_print.call_args_list]
        assert any("截图文件不存在" in msg for msg in print_calls)


class TestStatusMessages:
    """测试状态消息格式化功能"""
    
    def test_format_status_message_basic(self):
        """测试基本状态消息格式化"""
        result = format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS)
        assert result == "✔️ 结果: [通过]"
        
        result = format_status_message(StatusIcons.WARNING, StatusMessages.TRY_FAIL_SKIP)
        assert result == "⚠️ 结果: [尝试失败-已跳过]"
    
    def test_format_status_message_with_step_id(self):
        """测试带步骤ID的状态消息格式化"""
        result = format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, "test_001")
        assert result == "✔️ 结果: [尝试成功] - 步骤 test_001"
    
    def test_format_status_message_with_error(self):
        """测试带错误信息的状态消息格式化"""
        result = format_status_message(
            StatusIcons.FAILURE, 
            StatusMessages.FAIL, 
            "test_001", 
            "AttributeError: 'Page' object has no attribute 'page13'"
        )
        expected = "❌ 结果: [失败] - 步骤 test_001 - AttributeError: 'Page' object has no attribute 'page13'"
        assert result == expected


if __name__ == '__main__':
    pytest.main(['-v', __file__])
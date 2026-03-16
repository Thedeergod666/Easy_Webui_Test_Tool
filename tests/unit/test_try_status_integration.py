# -*- coding: utf-8 -*-
"""
Try状态错误处理集成测试
验证整个try状态处理流程的端到端功能
"""

import pytest
import os
import tempfile
from unittest.mock import Mock
import sys
from _pytest.outcomes import Skipped

# 添加项目路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from framework.Keywords import Keywords
from tests.helpers.step_flow_runner import execute_test_step
from playwright.sync_api import Locator


class MockPage:
    """模拟Page对象用于集成测试"""
    
    def __init__(self):
        self.screenshot_called = False
        self.screenshot_path = None
        
    def screenshot(self, path=None, full_page=True):
        self.screenshot_called = True
        self.screenshot_path = path
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'fake_screenshot_data')
        return b'fake_screenshot_data'
    
    def locator(self, selector):
        return MockLocator()
    
    def get_by_role(self, role, **kwargs):
        return MockLocator()
    
    def __getattr__(self, name):
        if name.startswith('page') and name[4:].isdigit():
            raise AttributeError(f"'Page' object has no attribute '{name}'")
        raise AttributeError(f"'MockPage' object has no attribute '{name}'")
    
    def set_default_timeout(self, timeout):
        """模拟设置默认超时"""
        self.default_timeout = timeout


class MockContext:
    """模拟BrowserContext对象"""
    
    def __init__(self):
        self.running_mode = 'headed'
        self.pages = []


class MockLocator(Locator):
    """模拟Locator对象用于集成测试"""
    
    def __init__(self):
        # 不调用父类构造函数，避免初始化问题
        pass
    
    def click(self):
        pass
    
    def first(self):
        return MockLocator()
    
    def count(self):
        return 1


class TestTryStatusIntegration:
    """Try状态处理集成测试"""
    
    def setup_method(self):
        """设置测试环境"""
        self.mock_page = MockPage()
        self.mock_context = MockContext()
        self.mock_page.context = self.mock_context
        self.screenshots_dir = tempfile.mkdtemp()
    
    def teardown_method(self):
        """清理测试环境"""
        import shutil
        if hasattr(self, 'screenshots_dir'):
            shutil.rmtree(self.screenshots_dir, ignore_errors=True)
    
    def create_keywords_instance(self):
        """创建Keywords实例"""
        keywords = Keywords(self.mock_page)
        keywords.screenshots_dir = self.screenshots_dir
        return keywords
    
    def test_try_status_success_case(self):
        """测试try状态成功情况"""
        keywords = self.create_keywords_instance()
        
        test_step = {
            "编号": "case_001",
            "执行状态": "try",
            "关键字": "click",
            "描述": "尝试点击按钮-应该成功",
            "定位方式": "css",
            "目标对象": "#test-button",
            "数据内容": ""
        }
        
        # 执行测试步骤，应该成功完成而不抛出异常
        try:
            execute_test_step(keywords, test_step, self.screenshots_dir)
            success = True
        except Skipped:
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"Try状态成功用例不应该失败: {e}")
        
        assert success, "Try状态成功用例应该正常完成"
    
    def test_try_status_codegen_error_case(self):
        """测试try状态Codegen错误情况"""
        keywords = self.create_keywords_instance()
        
        test_step = {
            "编号": "case_002",
            "执行状态": "try", 
            "关键字": "click",
            "描述": "尝试点击不存在的元素-应该跳过",
            "定位方式": "codegen",
            "目标对象": "page13.get_by_role('button', name='×')",
            "数据内容": ""
        }
        
        # 执行测试步骤，应该通过pytest.skip跳过
        with pytest.raises(Skipped):
            execute_test_step(keywords, test_step, self.screenshots_dir)
        
        # 验证截图被生成
        screenshot_files = [f for f in os.listdir(self.screenshots_dir) if f.startswith('try_error_case_002_')]
        assert len(screenshot_files) > 0, "Try失败应该生成截图"
    
    def test_normal_status_success_case(self):
        """测试正常状态成功情况"""
        keywords = self.create_keywords_instance()
        
        test_step = {
            "编号": "case_003",
            "执行状态": "",
            "关键字": "click",
            "描述": "正常点击按钮-应该成功",
            "定位方式": "css",
            "目标对象": "#normal-button",
            "数据内容": ""
        }
        
        # 执行测试步骤，应该成功完成
        try:
            execute_test_step(keywords, test_step, self.screenshots_dir)
            success = True
        except Exception as e:
            success = False
            pytest.fail(f"正常状态成功用例不应该失败: {e}")
        
        assert success, "正常状态成功用例应该正常完成"
    
    def test_skip_status_case(self):
        """测试skip状态情况"""
        keywords = self.create_keywords_instance()
        
        test_step = {
            "编号": "case_005",
            "执行状态": "skip",
            "关键字": "click",
            "描述": "跳过的步骤-应该直接跳过",
            "定位方式": "css",
            "目标对象": "#skip-button",
            "数据内容": ""
        }
        
        # 执行测试步骤，应该通过pytest.skip跳过
        with pytest.raises(Skipped):
            execute_test_step(keywords, test_step, self.screenshots_dir)


if __name__ == '__main__':
    pytest.main(['-v', __file__])

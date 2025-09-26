# -*- coding: utf-8 -*-
"""
验证Try状态失败截图集成功能
"""

import pytest
import os
import tempfile
import sys
from unittest.mock import Mock

# 添加项目路径到sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from framework.Keywords import Keywords


class MockPage:
    """模拟Page对象"""
    
    def __init__(self):
        self.screenshot_called = False
        self.screenshot_path = None
        self.default_timeout = None
        
    def screenshot(self, path=None, full_page=True):
        self.screenshot_called = True
        self.screenshot_path = path
        if path:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, 'wb') as f:
                f.write(b'fake_screenshot_data_for_try_failure')
        return b'fake_screenshot_data_for_try_failure'
    
    def set_default_timeout(self, timeout):
        self.default_timeout = timeout
    
    def locator(self, selector):
        return MockLocator()
    
    def get_by_role(self, role, **kwargs):
        # 模拟会引发错误的情况（只在特定情况下）
        if hasattr(self, '_should_fail') and self._should_fail:
            raise ValueError("模拟的get_by_role失败")
        return MockLocator()


class MockContext:
    """模拟BrowserContext对象"""
    
    def __init__(self):
        self.running_mode = 'headed'
        self.pages = []


class MockLocator:
    """模拟Locator对象"""
    
    def click(self):
        pass


def test_try_status_screenshot_integration():
    """测试try状态失败截图集成功能"""
    # 创建临时目录
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 创建mock对象
        mock_page = MockPage()
        mock_page._should_fail = True  # 设置会失败
        mock_context = MockContext()
        mock_page.context = mock_context
        
        # 创建 mock report_logger
        mock_report_logger = Mock()
        mock_report_logger.start_step = Mock()
        mock_report_logger.end_step = Mock()
        
        # 创建Keywords实例
        keywords = Keywords(mock_page, mock_report_logger)
        keywords.screenshots_dir = temp_dir
        
        # 准备try状态测试步骤
        test_step = {
            "编号": "test_try_001",
            "执行状态": "try",
            "关键字": "click",
            "描述": "尝试点击会失败的元素",
            "定位方式": "codegen",
            "目标对象": "page13.get_by_role('button', name='×')",
            "数据内容": ""
        }
        
        # 执行关键字方法，预期会跳过而不是失败
        from _pytest.outcomes import Skipped
        try:
            keywords.click(**test_step)
            success = False  # 不应该执行到这里
        except Skipped:
            # pytest.skip()会引发Skipped异常，这是正常的try状态跳过
            success = True
        except Exception as e:
            # 不应该有其他异常
            success = False
            print(f"意外的异常: {e}")
        
        # 验证结果
        assert success, "try状态应该跳过而不是失败"
        
        # 验证截图是否生成
        assert mock_page.screenshot_called, "try状态失败应该生成截图"
        
        # 验证截图文件是否存在
        screenshot_files = [f for f in os.listdir(temp_dir) if f.startswith('try_error_test_try_001_')]
        assert len(screenshot_files) > 0, "应该生成try失败截图文件"
        
        # 验证截图文件内容
        screenshot_path = os.path.join(temp_dir, screenshot_files[0])
        assert os.path.exists(screenshot_path), "截图文件应该存在"
        
        with open(screenshot_path, 'rb') as f:
            content = f.read()
        assert content == b'fake_screenshot_data_for_try_failure', "截图内容应该正确"
        
        # 验证try失败截图信息是否被记录
        assert hasattr(keywords, '_try_failure_screenshots'), "应该记录try失败截图信息"
        assert len(keywords._try_failure_screenshots) > 0, "应该有try失败截图记录"
        
        try_screenshot_info = keywords._try_failure_screenshots[0]
        assert try_screenshot_info['step_id'] == 'test_try_001', "步骤ID应该正确"
        assert try_screenshot_info['path'] == screenshot_path, "截图路径应该正确"
        
        print("✅ Try状态失败截图集成功能测试通过")
        
    finally:
        # 清理临时目录
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    test_try_status_screenshot_integration()
    print("🎉 Try状态失败截图集成功能验证完成！")
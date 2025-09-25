# -*- coding: utf-8 -*-
"""
向后兼容性测试
确保新的动态URL匹配功能不会破坏现有功能
"""

import pytest
from unittest.mock import Mock, MagicMock
from framework.keywords.page_management import PageManagementMixin


class MockPage:
    """模拟Playwright Page对象"""
    def __init__(self, url: str, closed: bool = False):
        self._url = url
        self._closed = closed
    
    @property
    def url(self):
        return self._url
    
    def is_closed(self):
        return self._closed
    
    def close(self):
        self._closed = True
    
    def goto(self, url, timeout=None):
        self._url = url
    
    def evaluate(self, script, timeout=None):
        """模拟evaluate方法"""
        if 'readyState' in script:
            return 'complete'
        elif 'typeof window' in script:
            return 'object'
        return True
    
    def wait_for_load_state(self, state, timeout=None):
        """模拟等待加载状态"""
        pass
    
    def reload(self, timeout=None):
        """模拟页面重新加载"""
        pass


class MockContext:
    """模拟Playwright BrowserContext对象"""
    def __init__(self, pages=None):
        self.pages = pages or []
    
    def new_page(self):
        new_page = MockPage("about:blank")
        self.pages.append(new_page)
        return new_page
    
    def wait_for_event(self, event, timeout=None):
        """模拟等待事件"""
        # 简单模拟，不做实际等待
        pass


class CompatibilityTestMixin(PageManagementMixin):
    """向后兼容性测试用的Mixin子类"""
    
    def __init__(self):
        self.context = MockContext()
        self.active_page = None
        self.DEFAULT_TIMEOUT = 30000
    
    def _get_target_page(self, **kwargs):
        """简化的页面获取逻辑用于测试"""
        page_index_str = str(kwargs.get('页面', '')).strip()
        
        if not page_index_str:
            return self.active_page
        
        try:
            page_index = int(page_index_str) - 1
            if page_index < 0:
                raise ValueError("页码必须是正整数。")
            
            if page_index >= len(self.context.pages):
                raise ValueError(f"页面{page_index_str}不存在")
            
            return self.context.pages[page_index]
            
        except ValueError as e:
            raise ValueError(f"页面参数错误: {e}")


class TestBackwardCompatibility:
    """向后兼容性测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.page_mgmt = CompatibilityTestMixin()
        
        # 设置测试页面
        test_pages = [
            MockPage("https://example.com/home"),
            MockPage("https://example.com/about"),
            MockPage("https://test.example.com/contact"),
        ]
        self.page_mgmt.context.pages = test_pages
        self.page_mgmt.active_page = test_pages[0]
    
    def test_traditional_open_still_works(self):
        """测试传统的open操作仍然正常工作"""
        # 模拟传统的open调用，不包含任何模式字符
        original_url = self.page_mgmt.active_page.url
        
        # 执行open操作
        self.page_mgmt.open(数据内容="https://newsite.com")
        
        # 验证URL已改变
        assert self.page_mgmt.active_page.url == "https://newsite.com"
    
    def test_traditional_close_page_still_works(self):
        """测试传统的close_page操作仍然正常工作"""
        initial_count = len(self.page_mgmt.context.pages)
        
        # 使用页码关闭页面（传统方式）
        target_page = self.page_mgmt.context.pages[1]  # 第2个页面
        self.page_mgmt.close_page(数据内容="2")
        
        # 验证页面已关闭
        assert target_page.is_closed()
    
    def test_traditional_switch_to_page_still_works(self):
        """测试传统的switch_to_page操作仍然正常工作"""
        # 切换到页面2（传统方式）
        target_page = self.page_mgmt.context.pages[1]
        self.page_mgmt.switch_to_page(数据内容="2")
        
        # 验证已切换到正确页面
        assert self.page_mgmt.active_page == target_page
    
    def test_exact_url_operations_still_work(self):
        """测试精确URL操作仍然正常工作"""
        # 使用精确URL关闭页面
        target_url = "https://example.com/about"
        self.page_mgmt.close_page(数据内容=target_url)
        
        # 验证目标页面已关闭
        for page in self.page_mgmt.context.pages:
            if page.url == target_url:
                assert page.is_closed()
                break
        else:
            pytest.fail("页面未找到或未正确关闭")
    
    def test_configuration_defaults_are_backward_compatible(self):
        """测试默认配置向后兼容"""
        # 验证默认配置不会破坏现有行为
        config = self.page_mgmt.URL_PATTERN_CONFIG
        
        assert config['enable_pattern_matching'] is True  # 默认启用
        assert config['strict_matching'] is False  # 默认允许降级
        assert config['case_sensitive'] is False  # 默认不区分大小写
        assert config['max_pattern_length'] == 500  # 合理的默认长度限制
    
    def test_non_pattern_urls_bypass_pattern_matching(self):
        """测试普通URL绕过模式匹配"""
        # 普通URL不应触发模式匹配逻辑
        normal_urls = [
            "https://example.com",
            "http://test.com/path",
            "https://sub.domain.org/deep/path/file.html",
        ]
        
        for url in normal_urls:
            # 这些URL不包含模式字符，应该使用传统逻辑
            is_match, pattern_type, score = self.page_mgmt._match_url_pattern(url, url)
            assert is_match is True
            # 确保使用精确匹配而不是模式匹配
            from framework.keywords.page_management import UrlPatternType
            assert pattern_type == UrlPatternType.EXACT
            assert score == 1.0
    
    def test_empty_data_content_still_works(self):
        """测试空数据内容的向后兼容性"""
        # 空数据内容应该使用当前活动页面
        current_page = self.page_mgmt.active_page
        
        # close_page 空参数应该关闭当前活动页面
        original_count = len(self.page_mgmt.context.pages)
        result = self.page_mgmt.close_page(数据内容="")
        
        # 验证当前活动页面被关闭了
        assert current_page.is_closed()
    
    def test_invalid_page_numbers_still_handled_correctly(self):
        """测试无效页码仍然正确处理"""
        # 无效页码应该得到适当的错误处理
        with pytest.raises(ValueError):
            self.page_mgmt.switch_to_page(数据内容="4")  # 不存在的页面（只有3个页面）
        
        with pytest.raises(ValueError):
            self.page_mgmt.switch_to_page(数据内容="-1")   # 负数页码
    
    def test_performance_with_many_pages(self):
        """测试在多页面环境下的性能"""
        # 创建更多页面来测试性能
        import time
        
        # 添加更多页面
        for i in range(50):
            new_page = MockPage(f"https://page{i}.com")
            self.page_mgmt.context.pages.append(new_page)
        
        # 测试查找匹配页面的性能
        start_time = time.time()
        match_result = self.page_mgmt._find_matching_page("*page25*")
        end_time = time.time()
        
        # 性能应该是合理的（小于1秒）
        assert (end_time - start_time) < 1.0
        assert match_result.success is True
    
    def test_error_messages_are_informative(self):
        """测试错误信息是信息丰富的"""
        # 测试不存在的URL模式
        match_result = self.page_mgmt._find_matching_page("*nonexistent*")
        assert match_result.success is False
        
        # 测试无效的正则表达式
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "{regex:invalid[}", "test"
        )
        assert is_match is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
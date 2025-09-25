# -*- coding: utf-8 -*-
"""
URL动态匹配功能单元测试
测试动态URL匹配、通配符匹配、正则表达式匹配等功能
"""

import pytest
import re
from unittest.mock import Mock, MagicMock
from framework.keywords.page_management import PageManagementMixin, UrlPatternType, MatchResult


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


class MockContext:
    """模拟Playwright BrowserContext对象"""
    def __init__(self, pages=None):
        self.pages = pages or []
    
    def new_page(self):
        new_page = MockPage("about:blank")
        self.pages.append(new_page)
        return new_page


class TestPageManagementMixin(PageManagementMixin):
    """测试用的PageManagementMixin子类"""
    
    def __init__(self):
        self.context = MockContext()
        self.active_page = None
        self.DEFAULT_TIMEOUT = 30000


class TestUrlPatternMatching:
    """URL模式匹配测试类"""
    
    def setup_method(self):
        """测试前设置"""
        self.page_mgmt = TestPageManagementMixin()
        
        # 设置测试页面
        test_pages = [
            MockPage("https://example.com/home"),
            MockPage("https://agent.teleai.com.cn/square/market-chat/abc123?param=value"),
            MockPage("https://test.example.com/product/456"),
            MockPage("https://subdomain.example.org/path/to/resource"),
            MockPage("about:blank"),
        ]
        self.page_mgmt.context.pages = test_pages
        self.page_mgmt.active_page = test_pages[0]
    
    def test_exact_url_matching(self):
        """测试精确URL匹配"""
        # 测试精确匹配成功
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://example.com/home", 
            "https://example.com/home"
        )
        assert is_match is True
        assert pattern_type == UrlPatternType.EXACT
        assert score == 1.0
        
        # 测试精确匹配失败
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://example.com/home", 
            "https://example.com/other"
        )
        assert is_match is False
        assert score == 0.0
    
    def test_wildcard_matching(self):
        """测试通配符匹配"""
        # 测试单个通配符匹配
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://example.com/*",
            "https://example.com/home"
        )
        assert is_match is True
        assert pattern_type == UrlPatternType.WILDCARD
        assert score > 0
        
        # 测试问号通配符匹配
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://example.com/hom?",
            "https://example.com/home"
        )
        assert is_match is True
        assert pattern_type == UrlPatternType.WILDCARD
        
        # 测试通配符匹配失败
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://other.com/*",
            "https://example.com/home"
        )
        assert is_match is False
    
    def test_regex_matching(self):
        """测试正则表达式匹配"""
        # 测试有效的正则表达式匹配
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "{regex:https://agent\\.teleai\\.com\\.cn/square/market-chat/\\w+\\?.*}",
            "https://agent.teleai.com.cn/square/market-chat/abc123?param=value"
        )
        assert is_match is True
        assert pattern_type == UrlPatternType.REGEX
        assert score > 0
        
        # 测试正则表达式格式错误
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "{regex:invalid_regex[}",
            "https://example.com"
        )
        assert is_match is False
        assert pattern_type == UrlPatternType.REGEX
        
        # 测试缺少结束符的正则表达式
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "{regex:https://example.com",
            "https://example.com"
        )
        assert is_match is False
    
    def test_partial_matching(self):
        """测试部分匹配"""
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "example.com",
            "https://example.com/home"
        )
        assert is_match is True
        assert pattern_type == UrlPatternType.PARTIAL
        assert 0 < score < 1
    
    def test_case_sensitivity(self):
        """测试大小写敏感性"""
        # 默认不区分大小写
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "HTTPS://EXAMPLE.COM/HOME",
            "https://example.com/home"
        )
        assert is_match is True
        
        # 启用大小写敏感
        self.page_mgmt.URL_PATTERN_CONFIG['case_sensitive'] = True
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "HTTPS://EXAMPLE.COM/HOME",
            "https://example.com/home"
        )
        assert is_match is False
        
        # 恢复默认设置
        self.page_mgmt.URL_PATTERN_CONFIG['case_sensitive'] = False
    
    def test_find_matching_page(self):
        """测试查找匹配页面"""
        # 查找存在的页面
        match_result = self.page_mgmt._find_matching_page("*example.com*")
        assert match_result.success is True
        assert match_result.matched_page is not None
        assert "example.com" in match_result.matched_page.url
        
        # 查找不存在的页面
        match_result = self.page_mgmt._find_matching_page("nonexistent.com")
        assert match_result.success is False
        assert match_result.matched_page is None
    
    def test_extract_base_url(self):
        """测试提取基础URL"""
        # 测试通配符模式
        base_url = self.page_mgmt._extract_base_url("https://example.com/path/*")
        assert base_url == "https://example.com/path"
        
        # 测试正则表达式模式
        base_url = self.page_mgmt._extract_base_url(
            "{regex:https://agent\\.teleai\\.com\\.cn/square/market-chat/\\w+\\?.*}"
        )
        assert base_url == "https://agent.teleai.com.cn"
        
        # 测试精确URL
        base_url = self.page_mgmt._extract_base_url("https://example.com/exact/path")
        assert base_url == "https://example.com/exact/path"
    
    def test_pattern_length_limit(self):
        """测试模式长度限制"""
        # 设置很小的长度限制
        original_limit = self.page_mgmt.URL_PATTERN_CONFIG['max_pattern_length']
        self.page_mgmt.URL_PATTERN_CONFIG['max_pattern_length'] = 10
        
        long_pattern = "a" * 20
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            long_pattern, "test"
        )
        assert is_match is False
        assert score == 0.0
        
        # 恢复原始限制
        self.page_mgmt.URL_PATTERN_CONFIG['max_pattern_length'] = original_limit
    
    def test_disabled_pattern_matching(self):
        """测试禁用模式匹配"""
        # 禁用模式匹配
        self.page_mgmt.URL_PATTERN_CONFIG['enable_pattern_matching'] = False
        
        # 通配符应该被当作精确匹配
        is_match, pattern_type, score = self.page_mgmt._match_url_pattern(
            "https://example.com/*",
            "https://example.com/home"
        )
        assert is_match is False
        assert pattern_type == UrlPatternType.EXACT
        
        # 恢复设置
        self.page_mgmt.URL_PATTERN_CONFIG['enable_pattern_matching'] = True
    
    def test_configure_url_matching(self):
        """测试URL匹配配置"""
        # 测试配置更新
        original_config = self.page_mgmt.URL_PATTERN_CONFIG.copy()
        
        self.page_mgmt.configure_url_matching(
            enable_pattern_matching=False,
            strict_matching=True,
            case_sensitive=True,
            max_pattern_length=200
        )
        
        assert self.page_mgmt.URL_PATTERN_CONFIG['enable_pattern_matching'] is False
        assert self.page_mgmt.URL_PATTERN_CONFIG['strict_matching'] is True
        assert self.page_mgmt.URL_PATTERN_CONFIG['case_sensitive'] is True
        assert self.page_mgmt.URL_PATTERN_CONFIG['max_pattern_length'] == 200
        
        # 恢复原始配置
        self.page_mgmt.URL_PATTERN_CONFIG.update(original_config)
    
    def test_get_url_matching_config(self):
        """测试获取URL匹配配置"""
        config = self.page_mgmt.get_url_matching_config()
        assert isinstance(config, dict)
        assert 'enable_pattern_matching' in config
        assert 'strict_matching' in config
        assert 'case_sensitive' in config
        assert 'max_pattern_length' in config


class TestUrlMatchingIntegration:
    """URL匹配集成测试"""
    
    def setup_method(self):
        """测试前设置"""
        self.page_mgmt = TestPageManagementMixin()
        
        # 设置模拟页面
        test_pages = [
            MockPage("https://example.com/home"),
            MockPage("https://agent.teleai.com.cn/square/market-chat/abc123?param=value"),
            MockPage("https://test.example.com/product/456"),
        ]
        self.page_mgmt.context.pages = test_pages
        self.page_mgmt.active_page = test_pages[0]
    
    def test_complex_regex_patterns(self):
        """测试复杂正则表达式模式"""
        # 测试问题中提到的具体模式
        pattern = "{regex:https://agent\\.teleai\\.com\\.cn/square/market-chat/\\w+\\?.*}"
        target_url = "https://agent.teleai.com.cn/square/market-chat/abc123?param=value"
        
        match_result = self.page_mgmt._find_matching_page(pattern)
        assert match_result.success is True
        assert match_result.matched_page.url == target_url
        assert match_result.pattern_type == UrlPatternType.REGEX
    
    def test_multiple_wildcard_patterns(self):
        """测试多种通配符模式"""
        patterns_and_expected = [
            ("*example*", True),
            ("https://*.com/*", True),
            ("*teleai*", True),
            ("*nonexistent*", False),
        ]
        
        for pattern, should_match in patterns_and_expected:
            match_result = self.page_mgmt._find_matching_page(pattern)
            assert match_result.success == should_match, f"Pattern {pattern} failed"
    
    def test_fallback_strategies(self):
        """测试降级策略"""
        # 测试通配符模式的基础URL提取
        pattern = "https://example.com/path/*"
        base_url = self.page_mgmt._extract_base_url(pattern)
        assert base_url == "https://example.com/path"
        
        # 测试正则表达式模式的基础URL提取
        pattern = "{regex:https://agent\\.teleai\\.com\\.cn/.*}"
        base_url = self.page_mgmt._extract_base_url(pattern)
        assert "agent.teleai.com.cn" in base_url


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
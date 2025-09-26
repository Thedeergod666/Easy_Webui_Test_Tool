# tests/unit/test_comprehensive_improvements.py
"""
多页面切换机制综合改进测试

测试页面生命周期管理、性能优化、错误处理等所有改进
"""
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import time

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from framework.keywords.page_management import PageManagementMixin, UrlPatternType, MatchResult
from framework.keywords.performance_optimization import URLMatchingOptimizer
from framework.keywords.error_handling import ErrorRecoveryHandler, ErrorSeverity


class TestComprehensiveImprovements(unittest.TestCase):
    """综合改进测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建一个测试用的PageManagementMixin实例
        class TestPageManagement(PageManagementMixin):
            def __init__(self):
                # 模拟初始化
                self.context = Mock()
                self.context.pages = []
                self.active_page = None
                self.URL_PATTERN_CONFIG = {
                    'enable_pattern_matching': True,
                    'strict_matching': False,
                    'case_sensitive': False,
                    'max_pattern_length': 500,
                }
                
                # 手动调用父类初始化
                super().__init__()
        
        self.page_mgmt = TestPageManagement()
        
    def test_lifecycle_and_optimization_integration(self):
        """测试生命周期管理和性能优化的集成"""
        # 创建模拟页面
        mock_page1 = Mock()
        mock_page1.url = "https://example.com/page1"
        mock_page1.is_closed.return_value = False
        mock_page1.on = Mock()
        
        mock_page2 = Mock()
        mock_page2.url = "https://example.com/page2"
        mock_page2.is_closed.return_value = False
        mock_page2.on = Mock()
        
        # 添加到context
        self.page_mgmt.context.pages = [mock_page1, mock_page2]
        
        # 测试页面注册
        self.page_mgmt._register_existing_pages()
        
        # 验证生命周期管理器是否正确注册
        self.assertIsNotNone(self.page_mgmt.page_lifecycle_manager)
        self.assertEqual(len(self.page_mgmt.page_lifecycle_manager.page_references), 2)
        
        # 验证URL优化器是否正确工作
        self.assertIsNotNone(self.page_mgmt.url_optimizer)
        
        # 测试快速精确匹配
        exact_match = self.page_mgmt.url_optimizer.fast_exact_match("https://example.com/page1")
        self.assertEqual(exact_match, mock_page1)
        
        # 获取性能报告
        report = self.page_mgmt.get_performance_report()
        self.assertIsInstance(report, dict)
        self.assertIn('cache_statistics', report)
        self.assertIn('index_statistics', report)
        
    def test_optimized_url_matching(self):
        """测试优化的URL匹配功能"""
        # 创建模拟页面
        mock_page = Mock()
        mock_page.url = "https://test.example.com/api/v1/users"
        mock_page.is_closed.return_value = False
        
        self.page_mgmt.context.pages = [mock_page]
        
        # 测试精确匹配
        is_match, pattern_type, score = self.page_mgmt._optimized_match_url_pattern(
            "https://test.example.com/api/v1/users",
            "https://test.example.com/api/v1/users"
        )
        self.assertTrue(is_match)
        self.assertEqual(score, 1.0)
        self.assertEqual(pattern_type, UrlPatternType.EXACT)
        
        # 测试通配符匹配
        is_match, pattern_type, score = self.page_mgmt._optimized_match_url_pattern(
            "*example.com/api/*",
            "https://test.example.com/api/v1/users"
        )
        self.assertTrue(is_match)
        self.assertGreater(score, 0)
        self.assertEqual(pattern_type, UrlPatternType.WILDCARD)
        
        # 测试正则表达式匹配
        is_match, pattern_type, score = self.page_mgmt._optimized_match_url_pattern(
            "{regex:.*example\\.com/api/v\\d+/.*}",
            "https://test.example.com/api/v1/users"
        )
        self.assertTrue(is_match)
        self.assertGreater(score, 0)
        self.assertEqual(pattern_type, UrlPatternType.REGEX)
        
    def test_intelligent_page_validation(self):
        """测试智能页面状态验证"""
        # 测试正常页面
        normal_page = Mock()
        normal_page.is_closed.return_value = False
        normal_page.url = "https://example.com"
        normal_page.evaluate.return_value = "complete"
        
        result = self.page_mgmt._validate_page_state(normal_page, "test_page")
        self.assertTrue(result)
        
        # 测试about:blank页面（简化验证）
        blank_page = Mock()
        blank_page.is_closed.return_value = False
        blank_page.url = "about:blank"
        
        result = self.page_mgmt._validate_page_state(blank_page, "blank_page")
        self.assertTrue(result)  # 应该通过简化验证
        
        # 测试已关闭页面
        closed_page = Mock()
        closed_page.is_closed.return_value = True
        
        result = self.page_mgmt._validate_page_state(closed_page, "closed_page")
        self.assertFalse(result)
        
    def test_error_handling_integration(self):
        """测试错误处理集成"""
        # 测试safe_execute方法
        def successful_operation(**kwargs):
            return "success"
        
        def failing_operation(**kwargs):
            raise ValueError("Test error")
        
        def fallback_operation(**kwargs):
            return "fallback_result"
        
        # 测试成功操作
        result = self.page_mgmt.safe_execute(
            successful_operation, 
            "test_operation"
        )
        self.assertTrue(result.success)
        self.assertEqual(result.additional_info['result'], "success")
        
        # 测试失败操作（有降级策略）
        with patch('builtins.print'):  # 抑制打印输出
            result = self.page_mgmt.safe_execute(
                failing_operation,
                "test_operation", 
                fallback_func=fallback_operation
            )
        # 由于有降级策略，应该成功
        self.assertTrue(result.success)
        self.assertTrue(result.fallback_used)
        
    def test_memory_cleanup_workflow(self):
        """测试内存清理工作流程"""
        # 创建模拟页面
        mock_page1 = Mock()
        mock_page1.url = "https://example.com/page1"
        mock_page1.is_closed.return_value = False
        mock_page1.on = Mock()
        
        mock_page2 = Mock()
        mock_page2.url = "https://example.com/page2"
        mock_page2.is_closed.return_value = True  # 已关闭页面
        mock_page2.on = Mock()
        
        # 注册页面
        self.page_mgmt.page_lifecycle_manager.register_page(mock_page1, "page_1")
        self.page_mgmt.page_lifecycle_manager.register_page(mock_page2, "page_2")
        
        # 初始状态
        initial_count = len(self.page_mgmt.page_lifecycle_manager.page_references)
        self.assertEqual(initial_count, 2)
        
        # 执行清理
        cleaned_count = self.page_mgmt.page_lifecycle_manager.cleanup_all_invalid_references()
        
        # 验证已关闭页面被清理
        self.assertEqual(cleaned_count, 1)
        final_count = len(self.page_mgmt.page_lifecycle_manager.page_references)
        self.assertEqual(final_count, 1)
        
        # 测试内存状态获取
        status = self.page_mgmt.get_memory_status()
        self.assertIsInstance(status, dict)
        
    def test_performance_optimization_caching(self):
        """测试性能优化缓存机制"""
        optimizer = URLMatchingOptimizer(max_cache_size=5, cache_ttl=1)
        
        # 测试正则表达式缓存
        pattern = r"https://.*\.example\.com/.*"
        
        # 第一次编译（缓存未命中）
        compiled1 = optimizer.get_compiled_regex(pattern, "regex")
        self.assertIsNotNone(compiled1)
        self.assertEqual(optimizer.performance_stats['cache_misses'], 1)
        
        # 第二次获取（缓存命中）
        compiled2 = optimizer.get_compiled_regex(pattern, "regex")
        self.assertEqual(compiled1, compiled2)
        self.assertEqual(optimizer.performance_stats['cache_hits'], 1)
        
        # 测试缓存过期
        time.sleep(1.1)  # 等待缓存过期
        compiled3 = optimizer.get_compiled_regex(pattern, "regex")
        self.assertIsNotNone(compiled3)
        # 缓存过期，应该重新编译
        
    def test_url_indexing_performance(self):
        """测试URL索引性能"""
        optimizer = URLMatchingOptimizer()
        
        # 添加多个页面到索引
        pages = [
            ("https://example.com/page1", Mock()),
            ("https://example.com/page2", Mock()),
            ("https://test.com/api/v1", Mock()),
            ("https://test.com/api/v2", Mock()),
        ]
        
        for url, page_ref in pages:
            optimizer.add_page_to_index(url, page_ref)
        
        # 测试精确匹配性能
        start_time = time.time()
        result = optimizer.fast_exact_match("https://example.com/page1")
        end_time = time.time()
        
        self.assertIsNotNone(result)
        self.assertLess(end_time - start_time, 0.001)  # 应该非常快
        
        # 测试域名搜索
        domain_results = optimizer.fast_domain_search("https://test.com/anything")
        self.assertEqual(len(domain_results), 2)  # 应该找到2个test.com的页面
        
        # 获取性能报告
        report = optimizer.get_performance_report()
        self.assertGreater(report['index_statistics']['total_indexed_urls'], 0)
        self.assertGreater(report['index_statistics']['domain_count'], 0)
        
    def test_end_to_end_workflow(self):
        """测试端到端工作流程"""
        # 设置完整的测试场景
        mock_pages = []
        for i in range(3):
            mock_page = Mock()
            mock_page.url = f"https://example.com/page{i+1}"
            mock_page.is_closed.return_value = False
            mock_page.on = Mock()
            mock_page.evaluate.return_value = "complete"
            mock_pages.append(mock_page)
        
        self.page_mgmt.context.pages = mock_pages
        self.page_mgmt.active_page = mock_pages[0]
        
        # 注册现有页面
        self.page_mgmt._register_existing_pages()
        
        # 测试页面查找
        match_result = self.page_mgmt._find_matching_page("*example.com/page2*")
        self.assertTrue(match_result.success)
        self.assertEqual(match_result.matched_page, mock_pages[1])
        
        # 测试性能报告
        report = self.page_mgmt.get_performance_report()
        self.assertIn('cache_statistics', report)
        self.assertIn('index_statistics', report)
        self.assertIn('matching_statistics', report)
        
        # 测试内存清理
        self.page_mgmt.cleanup_memory()
        
        # 测试错误统计
        error_stats = self.page_mgmt.get_error_statistics()
        self.assertIsInstance(error_stats, dict)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
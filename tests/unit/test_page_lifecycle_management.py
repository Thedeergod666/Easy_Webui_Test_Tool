# tests/unit/test_page_lifecycle_management.py
"""
页面生命周期管理单元测试

测试页面引用自动清理机制和统一错误处理框架
"""
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from framework.keywords.page_management import PageLifecycleManager
from framework.keywords.error_handling import (
    ErrorRecoveryHandler, ErrorSeverity, RecoveryStrategy, PageOperationResult
)

class TestPageLifecycleManager(unittest.TestCase):
    """页面生命周期管理器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.lifecycle_manager = PageLifecycleManager()
        
    def test_manager_initialization(self):
        """测试管理器初始化"""
        self.assertEqual(len(self.lifecycle_manager.page_references), 0)
        self.assertEqual(len(self.lifecycle_manager.cleanup_history), 0)
        self.assertTrue(self.lifecycle_manager.cleanup_enabled)
        
    def test_register_page(self):
        """测试页面注册功能"""
        # 创建模拟页面对象
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.on = Mock()
        
        # 注册页面
        self.lifecycle_manager.register_page(mock_page, "page_1")
        
        # 验证注册结果
        self.assertEqual(len(self.lifecycle_manager.page_references), 1)
        self.assertIn("page_1", self.lifecycle_manager.page_references)
        
        # 验证事件监听器已设置
        mock_page.on.assert_called_once()
        
    def test_cleanup_invalid_references(self):
        """测试无效引用清理"""
        # 创建模拟页面对象（已关闭）
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.on = Mock()
        mock_page.is_closed.return_value = True
        
        # 注册页面
        self.lifecycle_manager.register_page(mock_page, "page_1")
        
        # 执行清理
        cleaned_count = self.lifecycle_manager.cleanup_all_invalid_references()
        
        # 验证清理结果
        self.assertEqual(cleaned_count, 1)
        self.assertEqual(len(self.lifecycle_manager.page_references), 0)
        self.assertGreater(len(self.lifecycle_manager.cleanup_history), 0)
        
    def test_get_memory_status(self):
        """测试内存状态获取"""
        # 创建模拟页面对象
        mock_page1 = Mock()
        mock_page1.url = "https://example1.com"
        mock_page1.on = Mock()
        mock_page1.is_closed.return_value = False
        
        mock_page2 = Mock()
        mock_page2.url = "https://example2.com"
        mock_page2.on = Mock()
        mock_page2.is_closed.return_value = True
        
        # 注册页面
        self.lifecycle_manager.register_page(mock_page1, "page_1")
        self.lifecycle_manager.register_page(mock_page2, "page_2")
        
        # 获取状态
        status = self.lifecycle_manager.get_memory_status()
        
        # 验证状态信息
        self.assertEqual(status['total_references'], 2)
        self.assertEqual(status['active_pages'], 1)  # 只有一个页面未关闭
        self.assertTrue(status['cleanup_enabled'])
        
    def test_enable_disable_cleanup(self):
        """测试启用/禁用清理功能"""
        # 初始状态应该是启用的
        self.assertTrue(self.lifecycle_manager.cleanup_enabled)
        
        # 禁用清理
        self.lifecycle_manager.enable_cleanup(False)
        self.assertFalse(self.lifecycle_manager.cleanup_enabled)
        
        # 重新启用清理
        self.lifecycle_manager.enable_cleanup(True)
        self.assertTrue(self.lifecycle_manager.cleanup_enabled)


class TestErrorRecoveryHandler(unittest.TestCase):
    """错误恢复处理器测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.error_handler = ErrorRecoveryHandler()
        
    def test_handler_initialization(self):
        """测试处理器初始化"""
        self.assertEqual(len(self.error_handler.recovery_history), 0)
        self.assertEqual(self.error_handler.max_retry_attempts, 3)
        self.assertIsInstance(self.error_handler.error_strategies, dict)
        
    def test_handle_page_not_found_error(self):
        """测试页面未找到错误处理"""
        result = self.error_handler.handle_error(
            'page_not_found',
            'Page 5 not found',
            {'page_count': 3}
        )
        
        self.assertIsInstance(result, PageOperationResult)
        self.assertEqual(result.error_severity, ErrorSeverity.WARNING)
        self.assertIn('Page 5 not found', result.error_message)
        
    def test_handle_critical_error(self):
        """测试严重错误处理"""
        result = self.error_handler.handle_error(
            'memory_insufficient',
            'Out of memory',
            {}
        )
        
        self.assertIsInstance(result, PageOperationResult)
        self.assertEqual(result.error_severity, ErrorSeverity.CRITICAL)
        self.assertFalse(result.success)
        
    def test_retry_strategy(self):
        """测试重试策略"""
        # 第一次重试
        result1 = self.error_handler.handle_error(
            'page_load_timeout',
            'Page load timeout',
            {'retry_count': 0}
        )
        
        self.assertEqual(result1.error_severity, ErrorSeverity.ERROR)
        self.assertEqual(result1.additional_info.get('retry_count'), 1)
        
        # 超过最大重试次数
        result2 = self.error_handler.handle_error(
            'page_load_timeout',
            'Page load timeout',
            {'retry_count': 3}
        )
        
        self.assertFalse(result2.success)
        
    def test_fallback_strategy(self):
        """测试降级策略"""
        def mock_fallback():
            return "fallback executed"
        
        result = self.error_handler.handle_error(
            'url_pattern_no_match',
            'No matching pattern',
            {},
            fallback_action=mock_fallback
        )
        
        self.assertTrue(result.success)
        self.assertTrue(result.fallback_used)
        self.assertEqual(result.additional_info['fallback_result'], "fallback executed")
        
    def test_get_fix_suggestions(self):
        """测试修复建议获取"""
        suggestions = self.error_handler._get_fix_suggestions(
            'page_not_found', 
            {'page_count': 3}
        )
        
        self.assertIsInstance(suggestions, list)
        self.assertGreater(len(suggestions), 0)
        self.assertTrue(any('页码' in suggestion for suggestion in suggestions))
        
    def test_recovery_statistics(self):
        """测试恢复统计功能"""
        # 处理几个错误
        self.error_handler.handle_error('page_not_found', 'Test error 1')
        self.error_handler.handle_error('url_pattern_no_match', 'Test error 2')
        self.error_handler.handle_error('page_not_found', 'Test error 3')
        
        # 获取统计信息
        stats = self.error_handler.get_recovery_statistics()
        
        self.assertEqual(stats['total'], 3)
        self.assertGreater(stats['avg_operation_time'], 0)
        self.assertIsInstance(stats['common_errors'], list)
        
        # 验证常见错误统计
        common_errors_dict = dict(stats['common_errors'])
        self.assertEqual(common_errors_dict.get('page_not_found'), 2)
        self.assertEqual(common_errors_dict.get('url_pattern_no_match'), 1)

    def test_empty_recovery_statistics_contract(self):
        """空历史场景也应返回完整统计字段"""
        stats = self.error_handler.get_recovery_statistics()

        self.assertEqual(stats['total'], 0)
        self.assertEqual(stats['success_count'], 0)
        self.assertEqual(stats['success_rate'], 0)
        self.assertEqual(stats['common_errors'], [])
        self.assertEqual(stats['avg_operation_time'], 0)


class TestErrorHandlingIntegration(unittest.TestCase):
    """错误处理集成测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.error_handler = ErrorRecoveryHandler()
        
    def test_complete_error_handling_workflow(self):
        """测试完整的错误处理工作流程"""
        # 模拟不同类型的错误处理场景
        error_scenarios = [
            ('page_not_found', 'Page 10 not found', {'page_count': 5}),
            ('url_pattern_invalid', 'Invalid regex pattern', {}),
            ('navigation_timeout', 'Navigation timeout', {'retry_count': 0}),
            ('memory_insufficient', 'Out of memory', {})
        ]
        
        results = []
        for error_type, message, context in error_scenarios:
            result = self.error_handler.handle_error(error_type, message, context)
            results.append((error_type, result))
        
        # 验证处理结果
        self.assertEqual(len(results), 4)
        
        # 验证不同严重程度的错误被正确分类
        severities = [result.error_severity for _, result in results]
        self.assertIn(ErrorSeverity.WARNING, severities)  # page_not_found
        self.assertIn(ErrorSeverity.ERROR, severities)    # url_pattern_invalid, navigation_timeout
        self.assertIn(ErrorSeverity.CRITICAL, severities) # memory_insufficient
        
        # 验证统计信息
        stats = self.error_handler.get_recovery_statistics()
        self.assertEqual(stats['total'], 4)
        
    def test_error_classification(self):
        """测试错误分类功能"""
        from framework.keywords.error_handling import UnifiedErrorHandlingMixin
        
        # 创建一个包含错误分类方法的测试类
        class TestMixin(UnifiedErrorHandlingMixin):
            def __init__(self):
                super().__init__()
        
        mixin = TestMixin()
        
        # 测试不同异常的分类
        timeout_error = Exception("TimeoutError: Operation timed out")
        page_error = Exception("Page index out of range")  # 修改为更明确的错误信息
        value_error = ValueError("Missing required parameter")
        
        self.assertEqual(
            mixin._classify_error(timeout_error, "navigation"), 
            'navigation_timeout'
        )
        self.assertEqual(
            mixin._classify_error(page_error, "switch_page"), 
            'page_not_found'
        )
        self.assertEqual(
            mixin._classify_error(value_error, "test_operation"), 
            'parameter_missing'
        )


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)

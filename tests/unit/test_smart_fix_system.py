# -*- coding: utf-8 -*-
"""
测试用例修复系统的单元测试
验证智能修复机制的各个组件功能
"""

import pytest
import re
from unittest.mock import Mock, patch, MagicMock
from playwright.sync_api import Error as PlaywrightError

# 导入测试目标
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from framework.keywords.error_analyzer import (
    StrictModeErrorAnalyzer, LocatorOptimizer, 
    ErrorType, ErrorAnalysisResult, LocatorSuggestion
)
from framework.keywords.smart_fix_engine import (
    AutoRetryMechanism, SmartErrorHandler, RetryConfig, RetryStrategy
)


class TestStrictModeErrorAnalyzer:
    """测试严格模式错误分析器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.analyzer = StrictModeErrorAnalyzer()
    
    def test_identify_strict_mode_violation(self):
        """测试严格模式违规识别"""
        error_message = """
        playwright._impl._errors.Error: LocatorAssertions.to_contain_text: 
        Error: strict mode violation: get_by_role("button") resolved to 13 elements:
          1) <button type="button" class="carousel-primary-btn">…</button> 
             aka get_by_role("button", name="开始创作")
          2) <button>1</button> aka get_by_role("button", name="1")
        """
        
        expression = 'expect(page1.get_by_role("button")).to_contain_text("开始创作")'
        
        result = self.analyzer.analyze_error(error_message, expression)
        
        assert result.error_type == ErrorType.STRICT_MODE_VIOLATION
        assert result.element_count == 13
        assert result.suggested_locator is not None
        assert result.suggested_locator.suggested_locator == 'get_by_role("button", name="开始创作")'
        assert result.confidence > 0.8
    
    def test_extract_element_details(self):
        """测试元素详情提取"""
        error_message = """
        1) <button type="button" class="carousel-primary-btn">…</button> 
           aka get_by_role("button", name="开始创作")
        2) <button>1</button> aka get_by_role("button", name="1")
        3) <button class="btn">确定</button> aka get_by_role("button", name="确定")
        """
        
        elements = self.analyzer._extract_element_details(error_message)
        
        assert len(elements) == 3
        assert elements[0]["index"] == 1
        assert elements[0]["tag"] == "button"
        assert "type" in elements[0]["attributes"]
        assert elements[0]["suggested_locator"] == 'get_by_role("button", name="开始创作")'
    
    def test_playwright_suggestion_extraction(self):
        """测试Playwright建议提取"""
        error_message = """
        strict mode violation: get_by_role("button") resolved to 13 elements:
          1) <button type="button" class="carousel-primary-btn">…</button> 
             aka get_by_role("button", name="开始创作")
        """
        
        suggestion = self.analyzer._extract_playwright_suggestion(error_message)
        
        assert suggestion is not None
        assert suggestion.suggested_locator == 'get_by_role("button", name="开始创作")'
        assert suggestion.confidence > 0.9
        assert suggestion.strategy == "playwright_official_suggestion"
    
    def test_expression_reconstruction(self):
        """测试表达式重构"""
        original_expression = 'expect(page1.get_by_role("button")).to_contain_text("开始创作")'
        suggestion = LocatorSuggestion(
            original_locator='get_by_role("button")',
            suggested_locator='get_by_role("button", name="开始创作")',
            confidence=0.95,
            strategy="test",
            reason="test"
        )
        
        fixed_expression = self.analyzer._reconstruct_expression(original_expression, suggestion)
        
        expected = 'expect(page1.get_by_role("button", name="开始创作")).to_contain_text("开始创作")'
        assert fixed_expression == expected
    
    def test_timeout_error_analysis(self):
        """测试超时错误分析"""
        error_message = "Timeout 10000ms exceeded. waiting for get_by_text('应用产品')"
        expression = 'expect(page.get_by_text("应用产品")).to_be_visible()'
        
        result = self.analyzer.analyze_error(error_message, expression)
        
        assert result.error_type == ErrorType.ELEMENT_TIMEOUT
        assert result.error_info["timeout_ms"] == 10000
        assert "增加等待时间" in result.recovery_strategies
    
    def test_empty_content_error_analysis(self):
        """测试内容为空错误分析"""
        error_message = 'expected to contain text "星河AI赋能平台" Actual value: ""'
        expression = 'expect(page.locator("#product-app")).to_contain_text("星河AI赋能平台")'
        
        result = self.analyzer.analyze_error(error_message, expression)
        
        assert result.error_type == ErrorType.EMPTY_CONTENT
        assert result.error_info["expected_text"] == "星河AI赋能平台"
        assert "等待元素内容加载完成" in result.recovery_strategies
    
    def test_variable_undefined_error_analysis(self):
        """测试变量未定义错误分析"""
        error_message = "name 'page2' is not defined"
        expression = 'expect(page2.get_by_text("test")).to_be_visible()'
        
        result = self.analyzer.analyze_error(error_message, expression)
        
        assert result.error_type == ErrorType.VARIABLE_UNDEFINED
        assert result.error_info["undefined_variable"] == "page2"
        assert "检查页面变量是否存在" in result.recovery_strategies


class TestLocatorOptimizer:
    """测试定位器优化器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.optimizer = LocatorOptimizer()
    
    def test_add_name_attribute_strategy(self):
        """测试添加name属性策略"""
        error_result = ErrorAnalysisResult(
            error_type=ErrorType.STRICT_MODE_VIOLATION,
            original_expression='expect(page1.get_by_role("button")).to_contain_text("开始创作")',
            element_count=13,
            element_details=[{
                "index": 1,
                "tag": "button", 
                "suggested_locator": 'get_by_role("button", name="开始创作")'
            }]
        )
        
        optimized = self.optimizer._add_name_attribute(error_result)
        
        assert optimized == 'get_by_role("button", name="开始创作")'
    
    def test_add_first_selector_strategy(self):
        """测试添加first选择器策略"""
        error_result = ErrorAnalysisResult(
            error_type=ErrorType.STRICT_MODE_VIOLATION,
            original_expression='expect(page.get_by_text("确定")).to_be_visible()',
            element_count=2
        )
        
        optimized = self.optimizer._add_first_selector(error_result)
        
        assert optimized == 'get_by_text("确定").first'
    
    def test_add_filter_has_text_strategy(self):
        """测试添加filter has_text策略"""
        error_result = ErrorAnalysisResult(
            error_type=ErrorType.STRICT_MODE_VIOLATION,
            original_expression='expect(page.get_by_role("button")).to_contain_text("确定")',
            element_count=5
        )
        
        optimized = self.optimizer._add_filter_has_text(error_result)
        
        assert optimized == 'get_by_role("button").filter(has_text="确定")'
    
    def test_optimize_locator_with_suggestion(self):
        """测试使用建议优化定位器"""
        suggestion = LocatorSuggestion(
            original_locator='get_by_role("button")',
            suggested_locator='get_by_role("button", name="开始创作")',
            confidence=0.95,
            strategy="playwright_official",
            reason="test"
        )
        
        error_result = ErrorAnalysisResult(
            error_type=ErrorType.STRICT_MODE_VIOLATION,
            original_expression='test',
            suggested_locator=suggestion
        )
        
        optimized = self.optimizer.optimize_locator(error_result)
        
        assert optimized == 'get_by_role("button", name="开始创作")'


class TestAutoRetryMechanism:
    """测试自动重试机制"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,  # 使用更小的延迟加快测试
            debug_output=False  # 减少测试输出
        )
        self.retry_mechanism = AutoRetryMechanism(self.config)
    
    def test_successful_execution_no_retry(self):
        """测试成功执行无需重试"""
        expression = "1 + 1"
        context = {}
        
        result = self.retry_mechanism.execute_with_retry(expression, context)
        
        assert result == 2
        assert len(self.retry_mechanism.fix_history) == 1
        assert self.retry_mechanism.fix_history[0].success == True
    
    def test_failed_execution_with_retry(self):
        """测试失败执行触发重试"""
        expression = "undefined_variable"
        context = {}
        
        with pytest.raises(NameError):
            self.retry_mechanism.execute_with_retry(expression, context)
        
        assert len(self.retry_mechanism.fix_history) == 3  # 3次尝试
        assert all(not attempt.success for attempt in self.retry_mechanism.fix_history)
    
    @patch('framework.keywords.smart_fix_engine.time.sleep')
    def test_retry_delay_calculation(self, mock_sleep):
        """测试重试延迟计算"""
        expression = "invalid_expression"
        context = {}
        
        with pytest.raises(NameError):
            self.retry_mechanism.execute_with_retry(expression, context)
        
        # 验证sleep被调用了适当的次数（重试之间的延迟）
        assert mock_sleep.call_count == 2  # 第2和第3次尝试前的延迟
    
    def test_strict_mode_violation_fix(self):
        """测试严格模式违规修复"""
        # 模拟严格模式违规错误
        class MockPlaywrightError(Exception):
            def __str__(self):
                return """strict mode violation: get_by_role("button") resolved to 2 elements:
                  1) <button>开始创作</button> aka get_by_role("button", name="开始创作")"""
        
        expression = 'expect(page.get_by_role("button")).to_contain_text("开始创作")'
        
        # 模拟页面对象
        mock_page = Mock()
        mock_locator = Mock()
        mock_page.get_by_role.return_value = mock_locator
        
        context = {
            "page": mock_page,
            "expect": Mock()
        }
        
        # 第一次调用失败，第二次成功
        call_count = 0
        def mock_eval(expr, ctx):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise MockPlaywrightError()
            return True  # 成功
        
        with patch('builtins.eval', side_effect=mock_eval):
            result = self.retry_mechanism.execute_with_retry(expression, context)
        
        assert result == True
        assert len(self.retry_mechanism.fix_history) == 2
        assert self.retry_mechanism.fix_history[0].success == False
        assert self.retry_mechanism.fix_history[1].success == True
    
    def test_get_fix_summary(self):
        """测试获取修复摘要"""
        # 先清空历史
        self.retry_mechanism.clear_history()
        
        # 手动添加一些修复记录
        from framework.keywords.smart_fix_engine import FixAttempt
        
        self.retry_mechanism.fix_history.append(FixAttempt(
            attempt_number=1,
            strategy=RetryStrategy.IMMEDIATE,
            fixed_expression="test1",
            success=False,
            error_message="error1",
            execution_time=0.1
        ))
        
        self.retry_mechanism.fix_history.append(FixAttempt(
            attempt_number=2,
            strategy=RetryStrategy.LOCATOR_FIX,
            fixed_expression="test2",
            success=True,
            execution_time=0.2
        ))
        
        summary = self.retry_mechanism.get_fix_summary()
        
        assert summary["total_attempts"] == 2
        assert summary["successful_attempts"] == 1
        assert summary["failed_attempts"] == 1
        assert summary["success"] == True
        assert summary["total_execution_time"] == pytest.approx(0.3, rel=1e-6)
        assert RetryStrategy.IMMEDIATE in summary["strategies_used"]
        assert RetryStrategy.LOCATOR_FIX in summary["strategies_used"]


class TestSmartErrorHandler:
    """测试智能错误处理器"""
    
    def setup_method(self):
        """设置测试环境"""
        self.config = RetryConfig(
            max_attempts=2,
            base_delay=0.05,
            debug_output=False
        )
        self.handler = SmartErrorHandler(self.config)
    
    def test_recoverable_error_detection(self):
        """测试可恢复错误检测"""
        # 严格模式违规错误
        strict_error = Exception("strict mode violation: get_by_role resolved to 2 elements")
        assert self.handler._is_recoverable_error(strict_error) == True
        
        # 超时错误
        timeout_error = Exception("Timeout 10000ms exceeded waiting for locator")
        assert self.handler._is_recoverable_error(timeout_error) == True
        
        # 变量未定义错误
        name_error = NameError("name 'page2' is not defined")
        assert self.handler._is_recoverable_error(name_error) == True
        
        # 不可恢复错误
        type_error = TypeError("unsupported operand type")
        assert self.handler._is_recoverable_error(type_error) == False
    
    def test_handle_recoverable_error(self):
        """测试处理可恢复错误"""
        class MockStrictError(Exception):
            def __str__(self):
                return "strict mode violation: get_by_role resolved to 2 elements"
        
        expression = "test_expression"
        context = {"test": "value"}
        
        # 模拟重试机制成功修复
        with patch.object(self.handler.retry_mechanism, 'execute_with_retry', return_value="success"):
            result = self.handler.handle_playwright_error(MockStrictError(), expression, context)
            assert result == "success"
    
    def test_handle_unrecoverable_error(self):
        """测试处理不可恢复错误"""
        type_error = TypeError("unsupported operand type")
        expression = "test_expression"
        context = {"test": "value"}
        
        with pytest.raises(TypeError):
            self.handler.handle_playwright_error(type_error, expression, context)


class TestIntegrationScenarios:
    """集成测试场景"""
    
    def test_real_strict_mode_error_flow(self):
        """测试真实严格模式错误流程"""
        # 模拟真实的Playwright错误信息
        error_message = """
        playwright._impl._errors.Error: LocatorAssertions.to_contain_text: 
        Error: strict mode violation: get_by_role("button") resolved to 13 elements:
          1) <button type="button" class="carousel-primary-btn">…</button> 
             aka get_by_role("button", name="开始创作")
          2) <button>1</button> aka get_by_role("button", name="1")
          3) <button>2</button> aka get_by_role("button", name="2")
        """
        
        original_expression = 'expect(page1.get_by_role("button")).to_contain_text("开始创作")'
        
        # 1. 错误分析
        analyzer = StrictModeErrorAnalyzer()
        analysis_result = analyzer.analyze_error(error_message, original_expression)
        
        assert analysis_result.error_type == ErrorType.STRICT_MODE_VIOLATION
        assert analysis_result.element_count == 13
        assert analysis_result.suggested_locator is not None
        
        # 2. 定位器优化
        optimizer = LocatorOptimizer()
        optimized_locator = optimizer.optimize_locator(analysis_result)
        
        assert optimized_locator == 'get_by_role("button", name="开始创作")'
        
        # 3. 表达式重构
        fixed_expression = analysis_result.fixed_expression
        expected_fixed = 'expect(page1.get_by_role("button", name="开始创作")).to_contain_text("开始创作")'
        
        assert fixed_expression == expected_fixed
    
    def test_multiple_error_types_handling(self):
        """测试多种错误类型处理"""
        analyzer = StrictModeErrorAnalyzer()
        
        # 测试不同的错误类型
        test_cases = [
            ("strict mode violation: locator resolved to 3 elements", ErrorType.STRICT_MODE_VIOLATION),
            ("Timeout 5000ms exceeded waiting for element", ErrorType.ELEMENT_TIMEOUT),
            ("Element is not visible", ErrorType.ELEMENT_NOT_VISIBLE),
            ('expected to contain text "test" Actual value: ""', ErrorType.EMPTY_CONTENT),
            ("name 'page3' is not defined", ErrorType.VARIABLE_UNDEFINED),
            ("LocatorAssertions.to_have_text failed", ErrorType.ASSERTION_FAILED),
            ("Some random error", ErrorType.UNKNOWN_ERROR)
        ]
        
        for error_msg, expected_type in test_cases:
            result = analyzer.analyze_error(error_msg, "test_expression")
            assert result.error_type == expected_type, f"Failed for error: {error_msg}"


if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v", "--tb=short"])
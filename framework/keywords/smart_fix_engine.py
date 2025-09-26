# -*- coding: utf-8 -*-
"""
智能修复器模块
基于错误分析结果提供自动修复和重试机制
"""

import time
import re
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

from .error_analyzer import (
    StrictModeErrorAnalyzer, LocatorOptimizer, 
    ErrorAnalysisResult, ErrorType, LocatorSuggestion
)


class RetryStrategy(Enum):
    """重试策略枚举"""
    IMMEDIATE = "immediate"           # 立即重试
    WAIT_AND_RETRY = "wait_and_retry"  # 等待后重试
    PAGE_RECOVERY = "page_recovery"    # 页面恢复后重试
    LOCATOR_FIX = "locator_fix"        # 修复定位器后重试
    NO_RETRY = "no_retry"              # 不重试


@dataclass
class RetryConfig:
    """重试配置"""
    max_attempts: int = 3
    base_delay: float = 0.5
    max_delay: float = 5.0
    backoff_factor: float = 1.5
    enable_page_recovery: bool = True
    enable_locator_optimization: bool = True
    debug_output: bool = True


@dataclass
class FixAttempt:
    """修复尝试记录"""
    attempt_number: int
    strategy: RetryStrategy
    fixed_expression: Optional[str]
    success: bool
    error_message: Optional[str] = None
    execution_time: float = 0.0


class AutoRetryMechanism:
    """自动重试机制"""
    
    def __init__(self, config: RetryConfig = None):
        """
        初始化自动重试机制
        
        Args:
            config: 重试配置
        """
        self.config = config or RetryConfig()
        self.error_analyzer = StrictModeErrorAnalyzer()
        self.locator_optimizer = LocatorOptimizer()
        self.fix_history: List[FixAttempt] = []
    
    def execute_with_retry(self, 
                          expression: str, 
                          execution_context: Dict[str, Any],
                          error_handler: Optional[Callable] = None) -> Any:
        """
        执行表达式并在失败时自动重试
        
        Args:
            expression: 要执行的表达式
            execution_context: 执行上下文（包含page, expect等变量）
            error_handler: 自定义错误处理函数
            
        Returns:
            执行结果
            
        Raises:
            Exception: 所有重试都失败时抛出最后一个异常
        """
        if self.config.debug_output:
            print(f"  [智能修复] 开始执行表达式: {expression}")
        
        last_exception = None
        current_expression = expression
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                if self.config.debug_output:
                    print(f"  [智能修复] 尝试 {attempt}/{self.config.max_attempts}")
                
                start_time = time.time()
                
                # 执行表达式
                result = eval(current_expression, execution_context)
                
                execution_time = time.time() - start_time
                
                # 记录成功的修复尝试
                self._record_fix_attempt(
                    attempt, RetryStrategy.IMMEDIATE, current_expression, 
                    True, None, execution_time
                )
                
                if self.config.debug_output:
                    if attempt > 1:
                        print(f"  [智能修复] ✓ 第{attempt}次尝试成功！")
                    else:
                        print(f"  [智能修复] ✓ 表达式执行成功")
                
                return result
                
            except Exception as e:
                last_exception = e
                execution_time = time.time() - start_time
                
                if self.config.debug_output:
                    print(f"  [智能修复] ✗ 第{attempt}次尝试失败: {type(e).__name__}: {e}")
                
                # 记录失败的修复尝试
                self._record_fix_attempt(
                    attempt, RetryStrategy.IMMEDIATE, current_expression,
                    False, str(e), execution_time
                )
                
                # 如果还有重试机会，分析错误并尝试修复
                if attempt < self.config.max_attempts:
                    fixed_expression = self._analyze_and_fix(str(e), current_expression, execution_context)
                    
                    if fixed_expression and fixed_expression != current_expression:
                        if self.config.debug_output:
                            print(f"  [智能修复] 💡 生成修复表达式: {fixed_expression}")
                        current_expression = fixed_expression
                        
                        # 添加延迟
                        delay = self._calculate_delay(attempt)
                        if delay > 0:
                            if self.config.debug_output:
                                print(f"  [智能修复] ⏱ 等待 {delay:.1f}s 后重试")
                            time.sleep(delay)
                    else:
                        if self.config.debug_output:
                            print(f"  [智能修复] ⚠ 无法生成有效修复，使用原表达式重试")
                        
                        # 添加延迟
                        delay = self._calculate_delay(attempt)
                        if delay > 0:
                            time.sleep(delay)
                else:
                    if self.config.debug_output:
                        print(f"  [智能修复] ✗ 所有重试都失败，抛出最后异常")
        
        # 所有重试都失败，抛出最后的异常
        if error_handler:
            error_handler(last_exception, self.fix_history)
        
        raise last_exception
    
    def _analyze_and_fix(self, error_message: str, expression: str, execution_context: Dict[str, Any]) -> Optional[str]:
        """
        分析错误并生成修复建议
        
        Args:
            error_message: 错误信息
            expression: 出错的表达式
            execution_context: 执行上下文
            
        Returns:
            修复后的表达式，如果无法修复则返回None
        """
        if self.config.debug_output:
            print(f"    [错误分析] 分析错误: {error_message}")
        
        # 使用错误分析器分析错误
        analysis_result = self.error_analyzer.analyze_error(error_message, expression)
        
        if self.config.debug_output:
            print(f"    [错误分析] 错误类型: {analysis_result.error_type.value}")
            print(f"    [错误分析] 置信度: {analysis_result.confidence:.2f}")
        
        # 尝试不同的修复策略
        fixed_expression = None
        
        # 1. 严格模式违规修复
        if analysis_result.error_type == ErrorType.STRICT_MODE_VIOLATION:
            fixed_expression = self._fix_strict_mode_violation(analysis_result, execution_context)
        
        # 2. 变量未定义修复
        elif analysis_result.error_type == ErrorType.VARIABLE_UNDEFINED:
            fixed_expression = self._fix_undefined_variable(analysis_result, execution_context)
        
        # 3. 元素超时修复
        elif analysis_result.error_type == ErrorType.ELEMENT_TIMEOUT:
            fixed_expression = self._fix_element_timeout(analysis_result, execution_context)
        
        # 4. 内容为空修复
        elif analysis_result.error_type == ErrorType.EMPTY_CONTENT:
            fixed_expression = self._fix_empty_content(analysis_result, execution_context)
        
        # 5. 使用定位器优化器
        if not fixed_expression and self.config.enable_locator_optimization:
            fixed_expression = self.locator_optimizer.optimize_locator(analysis_result)
        
        return fixed_expression
    
    def _fix_strict_mode_violation(self, analysis_result: ErrorAnalysisResult, execution_context: Dict[str, Any]) -> Optional[str]:
        """修复严格模式违规"""
        if self.config.debug_output:
            print(f"    [严格模式修复] 元素数量: {analysis_result.element_count}")
        
        # 优先使用Playwright建议
        if analysis_result.suggested_locator:
            suggested = analysis_result.suggested_locator.suggested_locator
            fixed = analysis_result.fixed_expression
            
            if self.config.debug_output:
                print(f"    [严格模式修复] 使用Playwright建议: {suggested}")
            
            return fixed
        
        # 使用定位器优化器
        return self.locator_optimizer.optimize_locator(analysis_result)
    
    def _fix_undefined_variable(self, analysis_result: ErrorAnalysisResult, execution_context: Dict[str, Any]) -> Optional[str]:
        """修复变量未定义错误"""
        undefined_var = analysis_result.error_info.get("undefined_variable")
        
        if not undefined_var or not undefined_var.startswith("page"):
            return None
        
        if self.config.debug_output:
            print(f"    [变量修复] 修复未定义变量: {undefined_var}")
        
        # 尝试映射到现有页面
        available_pages = []
        for key, value in execution_context.items():
            if key.startswith("page") and hasattr(value, "url"):
                available_pages.append(key)
        
        if available_pages:
            # 使用第一个可用页面替换
            replacement_var = available_pages[0]
            fixed_expression = analysis_result.original_expression.replace(undefined_var, replacement_var)
            
            if self.config.debug_output:
                print(f"    [变量修复] 使用 {replacement_var} 替换 {undefined_var}")
            
            return fixed_expression
        
        return None
    
    def _fix_element_timeout(self, analysis_result: ErrorAnalysisResult, execution_context: Dict[str, Any]) -> Optional[str]:
        """修复元素超时错误"""
        if self.config.debug_output:
            print(f"    [超时修复] 添加页面等待逻辑")
        
        # 在表达式前添加页面等待
        expression = analysis_result.original_expression
        
        # 检查是否已经有wait_for调用
        if "wait_for" not in expression:
            # 提取页面变量
            page_match = re.search(r'(page\w*)', expression)
            if page_match:
                page_var = page_match.group(1)
                wait_expression = f"{page_var}.wait_for_load_state('networkidle'); {expression}"
                
                if self.config.debug_output:
                    print(f"    [超时修复] 添加网络空闲等待: {wait_expression}")
                
                return wait_expression
        
        return None
    
    def _fix_empty_content(self, analysis_result: ErrorAnalysisResult, execution_context: Dict[str, Any]) -> Optional[str]:
        """修复内容为空错误"""
        if self.config.debug_output:
            print(f"    [内容修复] 添加元素状态等待")
        
        expression = analysis_result.original_expression
        
        # 在定位器后添加等待
        locator_match = re.search(r'((?:page\w*\.)?(?:get_by_\w+|locator)\([^)]+\))', expression)
        if locator_match:
            locator = locator_match.group(1)
            enhanced_locator = f"{locator}.wait_for(state='attached')"
            fixed_expression = expression.replace(locator, enhanced_locator)
            
            if self.config.debug_output:
                print(f"    [内容修复] 添加元素附加等待: {fixed_expression}")
            
            return fixed_expression
        
        return None
    
    def _calculate_delay(self, attempt: int) -> float:
        """计算重试延迟"""
        if not self.config.enable_page_recovery:
            return 0
        
        delay = self.config.base_delay * (self.config.backoff_factor ** (attempt - 1))
        return min(delay, self.config.max_delay)
    
    def _record_fix_attempt(self, 
                           attempt_number: int, 
                           strategy: RetryStrategy, 
                           expression: str, 
                           success: bool, 
                           error_message: Optional[str] = None,
                           execution_time: float = 0.0):
        """记录修复尝试"""
        fix_attempt = FixAttempt(
            attempt_number=attempt_number,
            strategy=strategy,
            fixed_expression=expression,
            success=success,
            error_message=error_message,
            execution_time=execution_time
        )
        self.fix_history.append(fix_attempt)
    
    def get_fix_summary(self) -> Dict[str, Any]:
        """获取修复摘要"""
        if not self.fix_history:
            return {"total_attempts": 0, "success": False}
        
        total_attempts = len(self.fix_history)
        successful_attempts = [attempt for attempt in self.fix_history if attempt.success]
        failed_attempts = [attempt for attempt in self.fix_history if not attempt.success]
        
        return {
            "total_attempts": total_attempts,
            "successful_attempts": len(successful_attempts),
            "failed_attempts": len(failed_attempts),
            "success": len(successful_attempts) > 0,
            "total_execution_time": sum(attempt.execution_time for attempt in self.fix_history),
            "strategies_used": list(set(attempt.strategy for attempt in self.fix_history)),
            "final_expression": self.fix_history[-1].fixed_expression if self.fix_history else None
        }
    
    def clear_history(self):
        """清空修复历史"""
        self.fix_history.clear()


class SmartErrorHandler:
    """智能错误处理器"""
    
    def __init__(self, retry_config: RetryConfig = None):
        """
        初始化智能错误处理器
        
        Args:
            retry_config: 重试配置
        """
        self.retry_mechanism = AutoRetryMechanism(retry_config)
        self.config = retry_config or RetryConfig()
    
    def handle_playwright_error(self, error: Exception, expression: str, execution_context: Dict[str, Any]) -> Any:
        """
        处理Playwright错误并尝试自动修复
        
        Args:
            error: 异常对象
            expression: 出错的表达式
            execution_context: 执行上下文
            
        Returns:
            修复后的执行结果
            
        Raises:
            Exception: 无法修复时重新抛出原异常
        """
        error_message = str(error)
        
        if self.config.debug_output:
            print(f"  [智能错误处理] 捕获到错误: {type(error).__name__}")
            print(f"  [智能错误处理] 错误信息: {error_message}")
        
        # 检查是否为可修复的错误类型
        if self._is_recoverable_error(error):
            try:
                return self.retry_mechanism.execute_with_retry(
                    expression, 
                    execution_context,
                    self._custom_error_handler
                )
            except Exception as retry_error:
                if self.config.debug_output:
                    print(f"  [智能错误处理] 自动修复失败，抛出原异常")
                raise error  # 抛出原异常而不是重试异常
        else:
            if self.config.debug_output:
                print(f"  [智能错误处理] 错误类型不可恢复，直接抛出")
            raise error
    
    def _is_recoverable_error(self, error: Exception) -> bool:
        """检查错误是否可恢复"""
        error_message = str(error)
        error_type = type(error).__name__
        
        # 可恢复的错误模式
        recoverable_patterns = [
            r"strict mode violation",
            r"resolved to \d+ elements",
            r"name '.*' is not defined", 
            r"Timeout.*exceeded",
            r"Element is not visible",
            r"Actual value:\s*\"\"",
            r"LocatorAssertions\.\w+"
        ]
        
        for pattern in recoverable_patterns:
            if re.search(pattern, error_message, re.IGNORECASE):
                return True
        
        # 特定的异常类型
        recoverable_types = [
            "Error",  # Playwright Error
            "AssertionError",
            "TimeoutError",
            "NameError"
        ]
        
        return error_type in recoverable_types
    
    def _custom_error_handler(self, final_error: Exception, fix_history: List[FixAttempt]):
        """自定义错误处理回调"""
        if self.config.debug_output:
            print(f"\n  [修复摘要] 最终修复失败，历史记录:")
            for i, attempt in enumerate(fix_history, 1):
                status = "✓" if attempt.success else "✗"
                print(f"    {status} 尝试{i}: {attempt.strategy.value} ({attempt.execution_time:.2f}s)")
                if attempt.error_message:
                    print(f"      错误: {attempt.error_message}")
            
            summary = self.retry_mechanism.get_fix_summary()
            print(f"  [修复摘要] 总共尝试: {summary['total_attempts']}, 成功: {summary['successful_attempts']}")
            print(f"  [修复摘要] 总耗时: {summary['total_execution_time']:.2f}s")


# 全局实例
default_error_handler = SmartErrorHandler()
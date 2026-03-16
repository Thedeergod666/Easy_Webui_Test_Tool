# -*- coding: utf-8 -*-
"""
智能修复器模块
基于错误分析结果提供自动修复和重试机制
"""

import ast
import re
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .error_analyzer import ErrorAnalysisResult, ErrorType, LocatorOptimizer, StrictModeErrorAnalyzer


class RetryStrategy(Enum):
    """重试策略枚举"""

    IMMEDIATE = "immediate"
    WAIT_AND_RETRY = "wait_and_retry"
    PAGE_RECOVERY = "page_recovery"
    LOCATOR_FIX = "locator_fix"
    NO_RETRY = "no_retry"


@dataclass
class RetryConfig:
    """重试配置"""

    max_attempts: int = 3
    base_delay: float = 0.0
    max_delay: float = 5.0
    backoff_factor: float = 1.5
    enable_page_recovery: bool = True
    enable_locator_optimization: bool = True
    debug_output: bool = False


@dataclass
class FixAttempt:
    """修复尝试记录"""

    attempt_number: int
    strategy: RetryStrategy
    fixed_expression: Optional[str]
    success: bool
    error_message: Optional[str] = None
    execution_time: float = 0.0


@dataclass
class RepairPlan:
    """单次修复计划。"""

    strategy: RetryStrategy
    fixed_expression: Optional[str] = None
    pre_action: Optional[Callable[[Dict[str, Any]], None]] = None


class AutoRetryMechanism:
    """自动重试机制"""

    def __init__(self, config: RetryConfig = None):
        self.config = config or RetryConfig()
        self.error_analyzer = StrictModeErrorAnalyzer()
        self.locator_optimizer = LocatorOptimizer()
        self.fix_history: List[FixAttempt] = []
        self._analysis_cache: Dict[tuple[str, str], Optional[RepairPlan]] = {}

    def execute_with_retry(
        self,
        expression: str,
        execution_context: Dict[str, Any],
        error_handler: Optional[Callable] = None,
        initial_error: Optional[Exception] = None,
    ) -> Any:
        """
        执行表达式并在失败时自动重试。
        """
        if self.config.debug_output:
            print(f"  [智能修复] 开始执行表达式: {expression}")

        current_expression = expression
        current_plan: Optional[RepairPlan] = None
        last_exception: Optional[Exception] = initial_error

        for attempt in range(1, self.config.max_attempts + 1):
            strategy = current_plan.strategy if current_plan else RetryStrategy.IMMEDIATE
            start_time = time.time()
            try:
                if self.config.debug_output:
                    print(f"  [智能修复] 尝试 {attempt}/{self.config.max_attempts}")

                if initial_error is not None and attempt == 1:
                    raise initial_error

                if current_plan and current_plan.pre_action:
                    current_plan.pre_action(execution_context)

                result = eval(current_expression, execution_context)
                execution_time = time.time() - start_time
                self._record_fix_attempt(
                    attempt,
                    strategy,
                    current_expression,
                    True,
                    None,
                    execution_time,
                )

                if self.config.debug_output:
                    if attempt > 1:
                        print(f"  [智能修复] [PASS] 第{attempt}次尝试成功")
                    else:
                        print("  [智能修复] [PASS] 表达式执行成功")
                return result
            except Exception as error:
                last_exception = error
                execution_time = time.time() - start_time
                self._record_fix_attempt(
                    attempt,
                    strategy,
                    current_expression,
                    False,
                    str(error),
                    execution_time,
                )

                if self.config.debug_output:
                    print(f"  [智能修复] [FAIL] 第{attempt}次尝试失败: {type(error).__name__}: {error}")

                if attempt >= self.config.max_attempts:
                    break

                current_plan = self._analyze_and_fix(str(error), current_expression, execution_context)
                if current_plan and current_plan.fixed_expression:
                    current_expression = current_plan.fixed_expression
                    if self.config.debug_output:
                        print(f"  [智能修复] 生成修复表达式: {current_expression}")
                elif self.config.debug_output:
                    print("  [智能修复] 无可用修复计划，继续使用原表达式重试")

                delay = self._calculate_delay(attempt, current_plan)
                if delay > 0:
                    if self.config.debug_output:
                        print(f"  [智能修复] 等待 {delay:.1f}s 后重试")
                    time.sleep(delay)

        if error_handler:
            error_handler(last_exception, self.fix_history)
        raise last_exception

    def _analyze_and_fix(
        self,
        error_message: str,
        expression: str,
        execution_context: Dict[str, Any],
    ) -> Optional[RepairPlan]:
        """分析错误并生成修复计划。"""
        cache_key = (error_message, expression)
        if cache_key in self._analysis_cache:
            return self._analysis_cache[cache_key]

        if self.config.debug_output:
            print(f"    [错误分析] 分析错误: {error_message}")

        analysis_result = self.error_analyzer.analyze_error(error_message, expression)
        if self.config.debug_output:
            print(f"    [错误分析] 错误类型: {analysis_result.error_type.value}")
            print(f"    [错误分析] 置信度: {analysis_result.confidence:.2f}")

        repair_plan: Optional[RepairPlan] = None

        if analysis_result.error_type == ErrorType.STRICT_MODE_VIOLATION:
            repair_plan = self._fix_strict_mode_violation(analysis_result)
        elif analysis_result.error_type == ErrorType.VARIABLE_UNDEFINED:
            repair_plan = self._fix_undefined_variable(analysis_result, execution_context)
        elif analysis_result.error_type == ErrorType.ELEMENT_TIMEOUT:
            repair_plan = self._fix_element_timeout(analysis_result)
        elif analysis_result.error_type == ErrorType.EMPTY_CONTENT:
            repair_plan = self._fix_empty_content(analysis_result)

        if not repair_plan and self.config.enable_locator_optimization:
            optimized_locator = self.locator_optimizer.optimize_locator(analysis_result)
            if optimized_locator:
                fixed_expression = self._replace_locator_in_expression(expression, optimized_locator)
                if fixed_expression and fixed_expression != expression:
                    repair_plan = RepairPlan(
                        strategy=RetryStrategy.LOCATOR_FIX,
                        fixed_expression=fixed_expression,
                    )

        self._analysis_cache[cache_key] = repair_plan
        return repair_plan

    def _fix_strict_mode_violation(self, analysis_result: ErrorAnalysisResult) -> Optional[RepairPlan]:
        """修复严格模式违规。"""
        fixed_expression = analysis_result.fixed_expression or self.locator_optimizer.optimize_locator(analysis_result)
        if fixed_expression and fixed_expression != analysis_result.original_expression:
            return RepairPlan(
                strategy=RetryStrategy.LOCATOR_FIX,
                fixed_expression=fixed_expression,
            )
        return None

    def _fix_undefined_variable(
        self,
        analysis_result: ErrorAnalysisResult,
        execution_context: Dict[str, Any],
    ) -> Optional[RepairPlan]:
        """修复变量未定义错误。"""
        undefined_var = analysis_result.error_info.get("undefined_variable")
        if not undefined_var or not undefined_var.startswith("page"):
            return None

        available_pages = [
            key
            for key, value in execution_context.items()
            if key.startswith("page") and hasattr(value, "url")
        ]
        if not available_pages:
            return None

        replacement_var = available_pages[0]
        fixed_expression = analysis_result.original_expression.replace(undefined_var, replacement_var)
        if fixed_expression == analysis_result.original_expression:
            return None
        return RepairPlan(
            strategy=RetryStrategy.PAGE_RECOVERY,
            fixed_expression=fixed_expression,
        )

    def _fix_element_timeout(self, analysis_result: ErrorAnalysisResult) -> Optional[RepairPlan]:
        """修复元素超时错误。"""
        page_name = self._extract_primary_page_name(analysis_result.original_expression)
        if not page_name:
            return None

        def wait_for_page_ready(execution_context: Dict[str, Any], target_page_name: str = page_name):
            page = execution_context.get(target_page_name)
            if page is None:
                raise NameError(f"页面变量不存在: {target_page_name}")
            page.wait_for_load_state("networkidle")

        return RepairPlan(
            strategy=RetryStrategy.WAIT_AND_RETRY,
            fixed_expression=analysis_result.original_expression,
            pre_action=wait_for_page_ready,
        )

    def _fix_empty_content(self, analysis_result: ErrorAnalysisResult) -> Optional[RepairPlan]:
        """修复内容为空错误。"""
        locator_expression = self._extract_locator_expression(analysis_result.original_expression)
        if not locator_expression:
            return None

        def wait_for_locator_content(
            execution_context: Dict[str, Any],
            locator_code: str = locator_expression,
        ):
            locator = eval(locator_code, execution_context)
            locator.wait_for(state="attached")

        return RepairPlan(
            strategy=RetryStrategy.WAIT_AND_RETRY,
            fixed_expression=analysis_result.original_expression,
            pre_action=wait_for_locator_content,
        )

    def _extract_primary_page_name(self, expression: str) -> Optional[str]:
        match = re.search(r"\b(page\w*)\b", expression)
        return match.group(1) if match else None

    def _extract_locator_expression(self, expression: str) -> Optional[str]:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError:
            return None

        call_node = tree.body
        if not isinstance(call_node, ast.Call) or not isinstance(call_node.func, ast.Attribute):
            return None

        expect_call = call_node.func.value
        if (
            isinstance(expect_call, ast.Call)
            and isinstance(expect_call.func, ast.Name)
            and expect_call.func.id == "expect"
            and expect_call.args
        ):
            return ast.unparse(expect_call.args[0])
        return None

    def _replace_locator_in_expression(self, expression: str, optimized_locator: str) -> Optional[str]:
        patterns = [
            r"(get_by_role\([^)]+\))",
            r"(get_by_text\([^)]+\))",
            r"(get_by_label\([^)]+\))",
            r"(locator\([^)]+\))",
            r"(get_by_placeholder\([^)]+\))",
        ]

        for pattern in patterns:
            if re.search(pattern, expression):
                return re.sub(pattern, optimized_locator, expression, count=1)
        return None

    def _calculate_delay(self, attempt: int, repair_plan: Optional[RepairPlan] = None) -> float:
        """计算重试延迟。"""
        if self.config.base_delay <= 0:
            return 0
        if not self.config.enable_page_recovery:
            return 0
        if repair_plan and (repair_plan.pre_action or repair_plan.strategy == RetryStrategy.LOCATOR_FIX):
            return 0

        delay = self.config.base_delay * (self.config.backoff_factor ** (attempt - 1))
        return min(delay, self.config.max_delay)

    def _record_fix_attempt(
        self,
        attempt_number: int,
        strategy: RetryStrategy,
        expression: Optional[str],
        success: bool,
        error_message: Optional[str] = None,
        execution_time: float = 0.0,
    ):
        """记录修复尝试。"""
        self.fix_history.append(
            FixAttempt(
                attempt_number=attempt_number,
                strategy=strategy,
                fixed_expression=expression,
                success=success,
                error_message=error_message,
                execution_time=execution_time,
            )
        )

    def get_fix_summary(self) -> Dict[str, Any]:
        """获取修复摘要。"""
        if not self.fix_history:
            return {"total_attempts": 0, "success": False}

        successful_attempts = [attempt for attempt in self.fix_history if attempt.success]
        failed_attempts = [attempt for attempt in self.fix_history if not attempt.success]

        return {
            "total_attempts": len(self.fix_history),
            "successful_attempts": len(successful_attempts),
            "failed_attempts": len(failed_attempts),
            "success": bool(successful_attempts),
            "total_execution_time": sum(attempt.execution_time for attempt in self.fix_history),
            "strategies_used": list({attempt.strategy for attempt in self.fix_history}),
            "final_expression": self.fix_history[-1].fixed_expression if self.fix_history else None,
        }

    def clear_history(self):
        """清空修复历史。"""
        self.fix_history.clear()


class SmartErrorHandler:
    """智能错误处理器"""

    def __init__(self, retry_config: RetryConfig = None):
        self.retry_mechanism = AutoRetryMechanism(retry_config)
        self.config = retry_config or RetryConfig()

    def handle_playwright_error(
        self,
        error: Exception,
        expression: str,
        execution_context: Dict[str, Any],
    ) -> Any:
        """处理 Playwright 错误并尝试自动修复。"""
        error_message = str(error)

        if self.config.debug_output:
            print(f"  [智能错误处理] 捕获到错误: {type(error).__name__}")
            print(f"  [智能错误处理] 错误信息: {error_message}")

        if not self._is_recoverable_error(error):
            if self.config.debug_output:
                print("  [智能错误处理] 错误类型不可恢复，直接抛出")
            raise error

        try:
            return self.retry_mechanism.execute_with_retry(
                expression,
                execution_context,
                self._custom_error_handler,
                initial_error=error,
            )
        except Exception:
            if self.config.debug_output:
                print("  [智能错误处理] 自动修复失败，抛出原异常")
            raise error

    def _is_recoverable_error(self, error: Exception) -> bool:
        """检查错误是否可恢复。"""
        error_message = str(error)
        error_type = type(error).__name__

        recoverable_patterns = [
            r"strict mode violation",
            r"resolved to \d+ elements",
            r"name '.*' is not defined",
            r"Timeout.*exceeded",
            r"Element is not visible",
            r'Actual value:\s*""',
            r"LocatorAssertions\.\w+",
        ]
        if any(re.search(pattern, error_message, re.IGNORECASE) for pattern in recoverable_patterns):
            return True

        recoverable_types = {"Error", "AssertionError", "TimeoutError", "NameError"}
        return error_type in recoverable_types

    def _custom_error_handler(self, final_error: Exception, fix_history: List[FixAttempt]):
        """自定义错误处理回调。"""
        if not self.config.debug_output:
            return

        print("\n  [修复摘要] 最终修复失败，历史记录:")
        for index, attempt in enumerate(fix_history, 1):
            status = "[PASS]" if attempt.success else "[FAIL]"
            print(f"    {status} 尝试{index}: {attempt.strategy.value} ({attempt.execution_time:.2f}s)")
            if attempt.error_message:
                print(f"      错误: {attempt.error_message}")

        summary = self.retry_mechanism.get_fix_summary()
        print(f"  [修复摘要] 总共尝试: {summary['total_attempts']}, 成功: {summary['successful_attempts']}")
        print(f"  [修复摘要] 总耗时: {summary.get('total_execution_time', 0):.2f}s")


default_error_handler = SmartErrorHandler()

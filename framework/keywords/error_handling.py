# -*- coding: utf-8 -*-
"""
统一错误处理模块
提供分级错误处理、智能恢复和一致性处理策略
"""

import time
import pytest
from enum import Enum
from typing import Optional, Dict, Any, Union, Callable
from dataclasses import dataclass


class ErrorSeverity(Enum):
    """错误严重程度分级"""
    INFO = "info"           # 信息级：记录日志继续执行
    WARNING = "warning"     # 警告级：自动修复尝试
    ERROR = "error"         # 错误级：降级策略
    CRITICAL = "critical"   # 严重级：测试中止


class RecoveryStrategy(Enum):
    """恢复策略类型"""
    IGNORE = "ignore"               # 忽略错误继续执行
    RETRY = "retry"                 # 重试操作
    FALLBACK = "fallback"           # 降级到备选方案
    MANUAL_FIX = "manual_fix"       # 手动修复提示
    TERMINATE = "terminate"         # 终止测试


@dataclass
class PageOperationResult:
    """页面操作结果数据结构"""
    success: bool                           # 操作是否成功
    error_severity: ErrorSeverity           # 错误严重程度
    error_message: Optional[str] = None     # 错误详细信息
    recovery_action: Optional[str] = None   # 执行的恢复动作
    fallback_used: bool = False            # 是否使用了降级策略
    operation_time: float = 0.0            # 操作耗时（秒）
    additional_info: Dict[str, Any] = None  # 额外信息
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class ErrorRecoveryHandler:
    """错误恢复处理器"""
    
    def __init__(self):
        self.recovery_history: list = []  # 恢复历史记录
        self.max_retry_attempts = 3      # 最大重试次数
        self.retry_delay = 1.0           # 重试延迟（秒）
        
        # 错误处理策略映射
        self.error_strategies = {
            # 页面相关错误
            'page_not_found': (ErrorSeverity.WARNING, RecoveryStrategy.FALLBACK),
            'page_closed': (ErrorSeverity.ERROR, RecoveryStrategy.MANUAL_FIX),
            'page_load_timeout': (ErrorSeverity.ERROR, RecoveryStrategy.RETRY),
            
            # URL匹配相关错误
            'url_pattern_no_match': (ErrorSeverity.WARNING, RecoveryStrategy.FALLBACK),
            'url_pattern_invalid': (ErrorSeverity.ERROR, RecoveryStrategy.MANUAL_FIX),
            'url_pattern_timeout': (ErrorSeverity.ERROR, RecoveryStrategy.RETRY),
            
            # 导航相关错误
            'navigation_timeout': (ErrorSeverity.ERROR, RecoveryStrategy.RETRY),
            'navigation_failed': (ErrorSeverity.ERROR, RecoveryStrategy.FALLBACK),
            
            # 系统相关错误
            'memory_insufficient': (ErrorSeverity.CRITICAL, RecoveryStrategy.TERMINATE),
            'concurrent_conflict': (ErrorSeverity.ERROR, RecoveryStrategy.RETRY),
            
            # 配置相关错误
            'invalid_configuration': (ErrorSeverity.CRITICAL, RecoveryStrategy.TERMINATE),
            'parameter_missing': (ErrorSeverity.ERROR, RecoveryStrategy.MANUAL_FIX),
        }
    
    def handle_error(self, error_type: str, error_message: str, 
                    context: Dict[str, Any] = None, 
                    fallback_action: Optional[Callable] = None) -> PageOperationResult:
        """
        统一错误处理入口
        
        Args:
            error_type: 错误类型标识符
            error_message: 错误详细信息
            context: 错误上下文信息
            fallback_action: 降级策略回调函数
            
        Returns:
            PageOperationResult: 处理结果
        """
        start_time = time.time()
        context = context or {}
        
        # 获取错误处理策略
        severity, strategy = self.error_strategies.get(
            error_type, 
            (ErrorSeverity.ERROR, RecoveryStrategy.MANUAL_FIX)
        )
        
        print(f"  [错误处理] 检测到错误: {error_type}")
        print(f"    严重程度: {severity.value}")
        print(f"    恢复策略: {strategy.value}")
        print(f"    详细信息: {error_message}")
        
        # 根据策略执行处理
        result = self._execute_recovery_strategy(
            error_type, error_message, severity, strategy, 
            context, fallback_action
        )
        
        # 记录处理结果
        result.operation_time = time.time() - start_time
        self._record_recovery_history(error_type, result)
        
        return result
    
    def _execute_recovery_strategy(self, error_type: str, error_message: str,
                                 severity: ErrorSeverity, strategy: RecoveryStrategy,
                                 context: Dict[str, Any], 
                                 fallback_action: Optional[Callable]) -> PageOperationResult:
        """执行具体的恢复策略"""
        
        if strategy == RecoveryStrategy.IGNORE:
            print(f"    [恢复策略] 忽略错误，继续执行")
            return PageOperationResult(
                success=True,
                error_severity=severity,
                error_message=error_message,
                recovery_action="已忽略错误"
            )
        
        elif strategy == RecoveryStrategy.RETRY:
            print(f"    [恢复策略] 开始重试操作...")
            retry_count = context.get('retry_count', 0)
            
            if retry_count < self.max_retry_attempts:
                print(f"      重试第 {retry_count + 1} 次（最大 {self.max_retry_attempts} 次）")
                time.sleep(self.retry_delay)
                
                # 这里应该由调用者实现具体的重试逻辑
                return PageOperationResult(
                    success=False,  # 标记为需要重试
                    error_severity=severity,
                    error_message=error_message,
                    recovery_action=f"准备重试第 {retry_count + 1} 次",
                    additional_info={'retry_count': retry_count + 1}
                )
            else:
                print(f"      重试次数已达上限，转为手动修复策略")
                return self._execute_recovery_strategy(
                    error_type, error_message, severity, 
                    RecoveryStrategy.MANUAL_FIX, context, fallback_action
                )
        
        elif strategy == RecoveryStrategy.FALLBACK:
            print(f"    [恢复策略] 尝试降级策略...")
            
            if fallback_action:
                try:
                    fallback_result = fallback_action()
                    print(f"      降级策略执行成功")
                    return PageOperationResult(
                        success=True,
                        error_severity=severity,
                        error_message=error_message,
                        recovery_action="降级策略成功",
                        fallback_used=True,
                        additional_info={'fallback_result': fallback_result}
                    )
                except Exception as fallback_error:
                    print(f"      降级策略执行失败: {fallback_error}")
                    return PageOperationResult(
                        success=False,
                        error_severity=ErrorSeverity.ERROR,
                        error_message=f"原错误: {error_message}; 降级失败: {fallback_error}",
                        recovery_action="降级策略失败"
                    )
            else:
                print(f"      无可用的降级策略")
                return PageOperationResult(
                    success=False,
                    error_severity=severity,
                    error_message=error_message,
                    recovery_action="无降级策略可用"
                )
        
        elif strategy == RecoveryStrategy.MANUAL_FIX:
            print(f"    [恢复策略] 需要手动修复")
            
            # 提供详细的修复建议
            fix_suggestions = self._get_fix_suggestions(error_type, context)
            if fix_suggestions:
                print(f"      修复建议:")
                for suggestion in fix_suggestions:
                    print(f"        - {suggestion}")
            
            return PageOperationResult(
                success=False,
                error_severity=severity,
                error_message=error_message,
                recovery_action="需要手动修复",
                additional_info={'fix_suggestions': fix_suggestions}
            )
        
        elif strategy == RecoveryStrategy.TERMINATE:
            print(f"    [恢复策略] 严重错误，测试终止")
            return PageOperationResult(
                success=False,
                error_severity=severity,
                error_message=error_message,
                recovery_action="测试终止"
            )
        
        else:
            print(f"    [恢复策略] 未知策略: {strategy}")
            return PageOperationResult(
                success=False,
                error_severity=ErrorSeverity.ERROR,
                error_message=f"未知恢复策略: {strategy}",
                recovery_action="策略未实现"
            )
    
    def _get_fix_suggestions(self, error_type: str, context: Dict[str, Any]) -> list:
        """获取错误修复建议"""
        suggestions_map = {
            'page_not_found': [
                "检查页码是否在有效范围内",
                "使用 diagnose_page_issues 关键字查看当前页面状态",
                "确认页面是否已被关闭",
                "尝试使用 switch_to_page 切换到有效页面"
            ],
            'url_pattern_no_match': [
                "检查URL模式语法是否正确",
                "使用 diagnose_url_matching 关键字调试匹配问题",
                "确认目标页面是否已打开",
                "考虑使用部分匹配或模糊匹配"
            ],
            'url_pattern_invalid': [
                "检查正则表达式语法",
                "确认通配符使用正确",
                "验证模式字符串格式",
                "参考文档了解正确的模式语法"
            ],
            'page_closed': [
                "检查页面是否在操作前被意外关闭",
                "使用页面状态验证机制",
                "考虑增加页面存活检查",
                "实施页面恢复策略"
            ],
            'concurrent_conflict': [
                "检查是否有并发操作冲突",
                "使用页面锁机制",
                "调整操作时序",
                "增加同步点"
            ]
        }
        
        return suggestions_map.get(error_type, [
            "检查操作参数是否正确",
            "查看详细错误日志",
            "联系技术支持"
        ])
    
    def _record_recovery_history(self, error_type: str, result: PageOperationResult):
        """记录恢复历史"""
        history_entry = {
            'timestamp': time.time(),
            'error_type': error_type,
            'severity': result.error_severity.value,
            'success': result.success,
            'recovery_action': result.recovery_action,
            'operation_time': result.operation_time
        }
        
        self.recovery_history.append(history_entry)
        
        # 保持历史记录在合理大小
        if len(self.recovery_history) > 100:
            self.recovery_history = self.recovery_history[-50:]  # 保留最近50条
    
    def get_recovery_statistics(self) -> Dict[str, Any]:
        """获取恢复统计信息"""
        if not self.recovery_history:
            return {'total': 0, 'success_rate': 0, 'common_errors': []}
        
        total_count = len(self.recovery_history)
        success_count = sum(1 for entry in self.recovery_history if entry['success'])
        success_rate = success_count / total_count
        
        # 统计常见错误类型
        error_counts = {}
        for entry in self.recovery_history:
            error_type = entry['error_type']
            error_counts[error_type] = error_counts.get(error_type, 0) + 1
        
        common_errors = sorted(error_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return {
            'total': total_count,
            'success_count': success_count,
            'success_rate': success_rate,
            'common_errors': common_errors,
            'avg_operation_time': sum(entry['operation_time'] for entry in self.recovery_history) / total_count
        }


class UnifiedErrorHandlingMixin:
    """统一错误处理Mixin类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error_handler = ErrorRecoveryHandler()
    
    def handle_page_operation_error(self, operation_name: str, error: Exception, 
                                  **context) -> PageOperationResult:
        """
        页面操作错误的统一处理入口
        
        Args:
            operation_name: 操作名称
            error: 异常对象
            **context: 上下文信息
            
        Returns:
            PageOperationResult: 处理结果
        """
        # 分析错误类型
        error_type = self._classify_error(error, operation_name)
        error_message = f"{operation_name} 失败: {str(error)}"
        
        # 构建上下文信息
        error_context = {
            'operation': operation_name,
            'exception_type': type(error).__name__,
            'page_count': len(self.context.pages) if hasattr(self, 'context') else 0,
            **context
        }
        
        return self.error_handler.handle_error(error_type, error_message, error_context)
    
    def _classify_error(self, error: Exception, operation_name: str) -> str:
        """根据异常类型和操作上下文分类错误"""
        error_type_name = type(error).__name__
        error_message = str(error).lower()
        
        # 超时相关错误
        if 'timeout' in error_message or 'TimeoutError' in error_type_name:
            if 'navigation' in operation_name.lower():
                return 'navigation_timeout'
            elif 'page_load' in operation_name.lower():
                return 'page_load_timeout'
            else:
                return 'url_pattern_timeout'
        
        # 页面相关错误
        if 'page' in error_message:
            if 'closed' in error_message:
                return 'page_closed'
            elif 'not found' in error_message or 'index' in error_message:
                return 'page_not_found'
        
        # URL模式相关错误
        if any(keyword in error_message for keyword in ['pattern', 'regex', 'match']):
            if 'invalid' in error_message or 'syntax' in error_message:
                return 'url_pattern_invalid'
            else:
                return 'url_pattern_no_match'
        
        # 参数相关错误
        if 'ValueError' in error_type_name or 'missing' in error_message:
            return 'parameter_missing'
        
        # 内存相关错误
        if 'memory' in error_message or 'MemoryError' in error_type_name:
            return 'memory_insufficient'
        
        # 并发相关错误
        if any(keyword in error_message for keyword in ['lock', 'concurrent', 'thread']):
            return 'concurrent_conflict'
        
        # 默认为导航失败
        return 'navigation_failed'
    
    def safe_execute(self, operation_func: Callable, operation_name: str, 
                    fallback_func: Optional[Callable] = None, **kwargs) -> PageOperationResult:
        """
        安全执行操作的通用方法
        
        Args:
            operation_func: 要执行的操作函数
            operation_name: 操作名称
            fallback_func: 降级策略函数
            **kwargs: 传递给操作函数的参数
            
        Returns:
            PageOperationResult: 执行结果
        """
        start_time = time.time()
        
        try:
            result = operation_func(**kwargs)
            operation_time = time.time() - start_time
            
            return PageOperationResult(
                success=True,
                error_severity=ErrorSeverity.INFO,
                recovery_action="操作成功",
                operation_time=operation_time,
                additional_info={'result': result}
            )
            
        except Exception as e:
            print(f"    [安全执行] {operation_name} 执行失败: {e}")
            
            # 使用统一错误处理
            error_result = self.handle_page_operation_error(
                operation_name, e, 
                fallback_available=fallback_func is not None,
                **kwargs
            )
            
            # 如果有降级策略且错误处理建议使用降级
            if (fallback_func and 
                error_result.error_severity in [ErrorSeverity.WARNING, ErrorSeverity.ERROR]):
                
                try:
                    print(f"    [安全执行] 尝试降级策略...")
                    fallback_result = fallback_func(**kwargs)
                    operation_time = time.time() - start_time
                    
                    return PageOperationResult(
                        success=True,
                        error_severity=ErrorSeverity.WARNING,
                        error_message=str(e),
                        recovery_action="降级策略成功",
                        fallback_used=True,
                        operation_time=operation_time,
                        additional_info={'fallback_result': fallback_result}
                    )
                    
                except Exception as fallback_error:
                    print(f"    [安全执行] 降级策略也失败: {fallback_error}")
                    error_result.error_message += f"; 降级失败: {fallback_error}"
                    error_result.recovery_action = "降级策略失败"
            
            # 根据错误严重程度决定是否抛出异常
            if error_result.error_severity == ErrorSeverity.CRITICAL:
                pytest.fail(f"✗ 严重错误: {error_result.error_message}")
            elif error_result.error_severity == ErrorSeverity.ERROR and not error_result.fallback_used:
                pytest.fail(f"✗ {operation_name} 失败: {error_result.error_message}")
            
            return error_result
    
    def get_error_statistics(self):
        """
        [关键字] 获取错误处理统计信息
        用于监控和调试错误处理系统
        """
        stats = self.error_handler.get_recovery_statistics()
        print(f"执行 [错误统计]: 当前错误处理统计")
        print(f"  > 总处理次数: {stats['total']}")
        print(f"  > 成功恢复次数: {stats['success_count']}")
        print(f"  > 成功恢复率: {stats['success_rate']:.2%}")
        print(f"  > 平均处理时间: {stats['avg_operation_time']:.3f}秒")
        
        if stats['common_errors']:
            print(f"  > 常见错误类型:")
            for error_type, count in stats['common_errors']:
                print(f"    - {error_type}: {count}次")
        
        return stats
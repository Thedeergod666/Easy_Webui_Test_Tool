# -*- coding: utf-8 -*-
"""
错误分析引擎模块
智能分析Playwright错误信息，提供精确的修复建议
"""

import re
import json
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum


class ErrorType(Enum):
    """错误类型枚举"""
    STRICT_MODE_VIOLATION = "strict_mode_violation"
    ELEMENT_TIMEOUT = "element_timeout"
    ELEMENT_NOT_VISIBLE = "element_not_visible" 
    ASSERTION_FAILED = "assertion_failed"
    EMPTY_CONTENT = "empty_content"
    INVALID_LOCATOR = "invalid_locator"
    PAGE_STATE_INVALID = "page_state_invalid"
    VARIABLE_UNDEFINED = "variable_undefined"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class ErrorPattern:
    """错误模式定义"""
    pattern: str
    error_type: ErrorType
    description: str
    priority: int = 1  # 优先级，数字越大优先级越高


@dataclass
class LocatorSuggestion:
    """定位器建议"""
    original_locator: str
    suggested_locator: str
    confidence: float
    strategy: str
    reason: str


@dataclass
class ErrorAnalysisResult:
    """错误分析结果"""
    error_type: ErrorType
    original_expression: str
    element_count: int = 0
    element_details: List[Dict] = field(default_factory=list)
    suggested_locator: Optional[LocatorSuggestion] = None
    fixed_expression: Optional[str] = None
    confidence: float = 0.0
    error_info: Dict[str, Any] = field(default_factory=dict)
    recovery_strategies: List[str] = field(default_factory=list)


class StrictModeErrorAnalyzer:
    """严格模式错误分析器"""
    
    # 错误模式定义
    ERROR_PATTERNS = [
        ErrorPattern(
            pattern=r"strict mode violation",
            error_type=ErrorType.STRICT_MODE_VIOLATION,
            description="严格模式违规：定位器匹配多个元素",
            priority=10
        ),
        ErrorPattern(
            pattern=r"Timeout (\d+)ms exceeded.*?waiting for",
            error_type=ErrorType.ELEMENT_TIMEOUT,
            description="元素查找超时",
            priority=8
        ),
        ErrorPattern(
            pattern=r"Element is not visible",
            error_type=ErrorType.ELEMENT_NOT_VISIBLE,
            description="元素不可见",
            priority=7
        ),
        ErrorPattern(
            pattern=r'expected to contain text.*?Actual value:\s*""',
            error_type=ErrorType.EMPTY_CONTENT,
            description="断言内容为空",
            priority=6
        ),
        ErrorPattern(
            pattern=r"name '([^']+)' is not defined",
            error_type=ErrorType.VARIABLE_UNDEFINED,
            description="变量未定义",
            priority=5
        ),
        ErrorPattern(
            pattern=r"LocatorAssertions\.\w+",
            error_type=ErrorType.ASSERTION_FAILED,
            description="断言失败",
            priority=4
        )
    ]
    
    def __init__(self):
        """初始化错误分析器"""
        self.patterns = sorted(self.ERROR_PATTERNS, key=lambda x: x.priority, reverse=True)
    
    def analyze_error(self, error_message: str, expression: str) -> ErrorAnalysisResult:
        """
        分析错误信息，返回详细的分析结果
        
        Args:
            error_message: 错误消息
            expression: 出错的表达式
            
        Returns:
            ErrorAnalysisResult: 分析结果
        """
        # 1. 识别错误类型
        error_type = self._identify_error_type(error_message)
        
        # 2. 创建基础结果
        result = ErrorAnalysisResult(
            error_type=error_type,
            original_expression=expression,
            error_info={"raw_message": error_message}
        )
        
        # 3. 根据错误类型进行详细分析
        if error_type == ErrorType.STRICT_MODE_VIOLATION:
            self._analyze_strict_mode_violation(error_message, expression, result)
        elif error_type == ErrorType.ELEMENT_TIMEOUT:
            self._analyze_element_timeout(error_message, expression, result)
        elif error_type == ErrorType.EMPTY_CONTENT:
            self._analyze_empty_content(error_message, expression, result)
        elif error_type == ErrorType.VARIABLE_UNDEFINED:
            self._analyze_variable_undefined(error_message, expression, result)
        else:
            self._analyze_generic_error(error_message, expression, result)
        
        return result
    
    def _identify_error_type(self, error_message: str) -> ErrorType:
        """识别错误类型"""
        for pattern in self.patterns:
            if re.search(pattern.pattern, error_message, re.IGNORECASE | re.DOTALL):
                return pattern.error_type
        return ErrorType.UNKNOWN_ERROR
    
    def _analyze_strict_mode_violation(self, error_message: str, expression: str, result: ErrorAnalysisResult):
        """分析严格模式违规错误"""
        # 提取元素数量
        count_match = re.search(r"resolved to (\d+) elements", error_message)
        if count_match:
            result.element_count = int(count_match.group(1))
        
        # 提取元素详情
        result.element_details = self._extract_element_details(error_message)
        
        # 提取Playwright建议
        suggestion = self._extract_playwright_suggestion(error_message)
        if suggestion:
            result.suggested_locator = suggestion
            result.confidence = 0.9  # 高置信度，因为是Playwright官方建议
            
            # 生成修复后的表达式
            result.fixed_expression = self._reconstruct_expression(expression, suggestion)
        
        # 添加恢复策略
        result.recovery_strategies = [
            "使用Playwright建议的精确定位器",
            "添加name属性进行精确定位",
            "使用first()选择器选择第一个元素",
            "使用更具体的定位策略"
        ]
    
    def _extract_element_details(self, error_message: str) -> List[Dict]:
        """从错误信息中提取元素详情"""
        elements = []
        
        # 先尝试简单模式（aka在同一行）
        simple_pattern = r'(\d+)\)\s*<([^>]+)>.*?aka\s+(.+?)(?=\n|$)'
        simple_matches = re.findall(simple_pattern, error_message, re.MULTILINE | re.DOTALL)
        
        if simple_matches:
            for match in simple_matches:
                index, tag_content, aka = match
                element_info = {
                    "index": int(index),
                    "tag": self._extract_tag_name(tag_content),
                    "attributes": self._extract_attributes(tag_content),
                    "suggested_locator": aka.strip()
                }
                elements.append(element_info)
        else:
            # 复杂模式（aka可能在下一行）
            lines = error_message.split('\n')
            current_element = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # 匹配元素行
                element_match = re.match(r'(\d+)\)\s*<([^>]+)>', line)
                if element_match:
                    if current_element:
                        elements.append(current_element)
                    
                    index, tag_content = element_match.groups()
                    current_element = {
                        "index": int(index),
                        "tag": self._extract_tag_name(tag_content),
                        "attributes": self._extract_attributes(tag_content)
                    }
                
                # 匹配aka行
                elif line.startswith('aka ') and current_element:
                    current_element["suggested_locator"] = line[4:].strip()
            
            # 添加最后一个元素
            if current_element:
                elements.append(current_element)
        
        return elements
    
    def _extract_tag_name(self, tag_content: str) -> str:
        """从标签内容中提取标签名"""
        match = re.match(r'^(\w+)', tag_content)
        return match.group(1) if match else "unknown"
    
    def _extract_attributes(self, tag_content: str) -> Dict[str, str]:
        """从标签内容中提取属性"""
        attributes = {}
        
        # 匹配属性格式：attribute="value"
        attr_pattern = r'(\w+)=(?:"([^"]*)"|\'([^\']*)\')' 
        matches = re.findall(attr_pattern, tag_content)
        
        for match in matches:
            attr_name, value1, value2 = match
            attributes[attr_name] = value1 or value2
        
        return attributes
    
    def _extract_playwright_suggestion(self, error_message: str) -> Optional[LocatorSuggestion]:
        """提取Playwright的建议定位器"""
        # 查找第一个元素的aka建议
        pattern = r'1\).*?aka\s+(.+?)(?=\n|2\)|$)'
        match = re.search(pattern, error_message, re.DOTALL)
        
        if match:
            suggested_locator = match.group(1).strip()
            
            # 解析原始定位器
            original_locator = self._extract_original_locator_from_suggestion(suggested_locator)
            
            return LocatorSuggestion(
                original_locator=original_locator,
                suggested_locator=suggested_locator,
                confidence=0.95,
                strategy="playwright_official_suggestion",
                reason="Playwright官方在错误信息中提供的精确定位器建议"
            )
        
        return None
    
    def _extract_original_locator_from_suggestion(self, suggested_locator: str) -> str:
        """从建议定位器中提取原始定位器"""
        # 例如：get_by_role("button", name="开始创作") -> get_by_role("button")
        match = re.match(r'(get_by_\w+\([^,)]+)', suggested_locator)
        return match.group(1) + ')' if match else suggested_locator
    
    def _reconstruct_expression(self, original_expression: str, suggestion: LocatorSuggestion) -> str:
        """重构表达式，替换定位器"""
        if not suggestion:
            return original_expression
        
        # 查找原始定位器在表达式中的位置
        original_locator = suggestion.original_locator
        suggested_locator = suggestion.suggested_locator
        
        # 尝试直接替换
        if original_locator in original_expression:
            return original_expression.replace(original_locator, suggested_locator)
        
        # 更复杂的替换逻辑
        return self._smart_replace_locator(original_expression, suggested_locator)
    
    def _smart_replace_locator(self, expression: str, suggested_locator: str) -> str:
        """智能替换定位器"""
        # 使用正则表达式查找并替换定位器
        patterns = [
            r'(get_by_role\([^)]+\))',
            r'(get_by_text\([^)]+\))',
            r'(get_by_label\([^)]+\))',
            r'(locator\([^)]+\))',
            r'(get_by_placeholder\([^)]+\))'
        ]
        
        for pattern in patterns:
            if re.search(pattern, expression):
                return re.sub(pattern, suggested_locator, expression, count=1)
        
        return expression
    
    def _analyze_element_timeout(self, error_message: str, expression: str, result: ErrorAnalysisResult):
        """分析元素超时错误"""
        # 提取超时时间
        timeout_match = re.search(r"Timeout (\d+)ms", error_message)
        if timeout_match:
            result.error_info["timeout_ms"] = int(timeout_match.group(1))
        
        # 提取等待的定位器
        waiting_pattern = r"waiting for (.+?)(?:\s|$)"
        waiting_match = re.search(waiting_pattern, error_message)
        if waiting_match:
            result.error_info["waiting_for"] = waiting_match.group(1)
        
        result.recovery_strategies = [
            "增加等待时间",
            "添加页面加载等待",
            "使用更具体的定位器",
            "检查元素是否在DOM中存在"
        ]
    
    def _analyze_empty_content(self, error_message: str, expression: str, result: ErrorAnalysisResult):
        """分析内容为空错误"""
        # 提取期望的文本
        expected_pattern = r'expected to contain text [\'"]([^\'"]+)[\'"]'
        expected_match = re.search(expected_pattern, error_message)
        if expected_match:
            result.error_info["expected_text"] = expected_match.group(1)
        
        result.recovery_strategies = [
            "等待元素内容加载完成",
            "检查元素的文本内容是否为动态加载",
            "使用to_have_text替代to_contain_text",
            "添加页面状态等待"
        ]
    
    def _analyze_variable_undefined(self, error_message: str, expression: str, result: ErrorAnalysisResult):
        """分析变量未定义错误"""
        # 提取未定义的变量名
        var_pattern = r"name '([^']+)' is not defined"
        var_match = re.search(var_pattern, error_message)
        if var_match:
            result.error_info["undefined_variable"] = var_match.group(1)
        
        result.recovery_strategies = [
            "检查页面变量是否存在",
            "使用页面索引访问",
            "等待页面创建完成",
            "使用active_page替代特定页面变量"
        ]
    
    def _analyze_generic_error(self, error_message: str, expression: str, result: ErrorAnalysisResult):
        """分析通用错误"""
        result.recovery_strategies = [
            "检查表达式语法",
            "验证页面状态",
            "重试执行",
            "添加异常处理"
        ]


class LocatorOptimizer:
    """定位器优化器"""
    
    def __init__(self):
        """初始化优化器"""
        self.optimization_strategies = [
            self._add_name_attribute,
            self._add_first_selector,
            self._add_filter_has_text,
            self._use_nth_selector,
            self._combine_locators
        ]
    
    def optimize_locator(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """
        优化定位器
        
        Args:
            error_result: 错误分析结果
            
        Returns:
            优化后的定位器字符串
        """
        if error_result.suggested_locator:
            # 如果有官方建议，优先使用
            return error_result.suggested_locator.suggested_locator
        
        # 应用优化策略
        for strategy in self.optimization_strategies:
            optimized = strategy(error_result)
            if optimized:
                return optimized
        
        return None
    
    def _add_name_attribute(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """添加name属性策略"""
        if error_result.error_type != ErrorType.STRICT_MODE_VIOLATION:
            return None
        
        # 从第一个元素的建议中提取name属性
        if error_result.element_details:
            first_element = error_result.element_details[0]
            if "suggested_locator" in first_element:
                suggested = first_element["suggested_locator"]
                name_match = re.search(r'name="([^"]+)"', suggested)
                if name_match:
                    name_value = name_match.group(1)
                    
                    # 构建新的定位器
                    expression = error_result.original_expression
                    role_match = re.search(r'get_by_role\("([^"]+)"\)', expression)
                    if role_match:
                        role = role_match.group(1)
                        return f'get_by_role("{role}", name="{name_value}")'
        
        return None
    
    def _add_first_selector(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """添加first选择器策略"""
        if error_result.error_type != ErrorType.STRICT_MODE_VIOLATION:
            return None
        
        expression = error_result.original_expression
        
        # 在定位器后添加.first
        locator_patterns = [
            r'(get_by_\w+\([^)]+\))',
            r'(locator\([^)]+\))'
        ]
        
        for pattern in locator_patterns:
            match = re.search(pattern, expression)
            if match:
                locator = match.group(1)
                return f"{locator}.first"
        
        return None
    
    def _add_filter_has_text(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """添加filter has_text策略"""
        if error_result.error_type != ErrorType.STRICT_MODE_VIOLATION:
            return None
        
        # 从表达式中提取期望的文本
        expression = error_result.original_expression
        text_match = re.search(r'to_contain_text\([\'"]([^\'"]+)[\'"]', expression)
        if text_match:
            expected_text = text_match.group(1)
            
            # 构建filter定位器
            locator_match = re.search(r'(get_by_\w+\([^)]+\))', expression)
            if locator_match:
                base_locator = locator_match.group(1)
                return f'{base_locator}.filter(has_text="{expected_text}")'
        
        return None
    
    def _use_nth_selector(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """使用nth选择器策略"""
        if error_result.error_type != ErrorType.STRICT_MODE_VIOLATION:
            return None
        
        expression = error_result.original_expression
        locator_match = re.search(r'(get_by_\w+\([^)]+\))', expression)
        if locator_match:
            base_locator = locator_match.group(1)
            return f"{base_locator}.nth(0)"
        
        return None
    
    def _combine_locators(self, error_result: ErrorAnalysisResult) -> Optional[str]:
        """组合定位器策略"""
        # 更复杂的组合策略，留待后续扩展
        return None


# 全局实例
error_analyzer = StrictModeErrorAnalyzer()
locator_optimizer = LocatorOptimizer()
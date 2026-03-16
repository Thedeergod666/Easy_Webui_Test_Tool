# -*- coding: utf-8 -*-
"""
元素定位模块
提供页面元素定位和查找相关的关键字
"""

import re
import ast
from playwright.sync_api import Page, Locator


class ElementLocatorMixin:
    """元素定位Mixin类
     
    提供页面元素定位和查找相关的方法实现。
    """
    
    def _evaluate_safe_ast_value(self, node, scope=None):
        """在受限作用域内求值参数 AST，只允许字面量和白名单调用。"""
        scope = scope or {}

        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            raise NameError(f"在安全作用域中找不到名字: '{node.id}'")
        if isinstance(node, ast.Tuple):
            return tuple(self._evaluate_safe_ast_value(item, scope) for item in node.elts)
        if isinstance(node, ast.List):
            return [self._evaluate_safe_ast_value(item, scope) for item in node.elts]
        if isinstance(node, ast.Dict):
            return {
                self._evaluate_safe_ast_value(key, scope): self._evaluate_safe_ast_value(value, scope)
                for key, value in zip(node.keys, node.values)
            }
        if isinstance(node, ast.UnaryOp):
            operand = self._evaluate_safe_ast_value(node.operand, scope)
            if isinstance(node.op, ast.USub):
                return -operand
            if isinstance(node.op, ast.UAdd):
                return +operand
            if isinstance(node.op, ast.Not):
                return not operand
            raise TypeError(f"不支持的一元运算: {type(node.op)}")
        if isinstance(node, ast.Attribute):
            parent_object = self._evaluate_safe_ast_value(node.value, scope)
            if parent_object is re:
                if hasattr(re, node.attr):
                    return getattr(re, node.attr)
                raise AttributeError(f"re 模块不存在属性: {node.attr}")
            raise TypeError(f"不支持的参数属性访问: {ast.unparse(node)}")
        if isinstance(node, ast.Call):
            callable_object = self._evaluate_safe_ast_value(node.func, scope)
            args = [self._evaluate_safe_ast_value(arg, scope) for arg in node.args]
            kwargs = {
                kw.arg: self._evaluate_safe_ast_value(kw.value, scope)
                for kw in node.keywords
            }
            if callable_object is re.compile:
                return callable_object(*args, **kwargs)
            raise TypeError(f"不支持的参数调用: {ast.unparse(node)}")

        raise TypeError(f"不支持的参数节点类型: {type(node)}")

    def _execute_codegen_node(self, node, scope):
        """
        [内部] 递归地执行AST（抽象语法树）节点。
        这是Codegen安全执行引擎的核心部分，用于解析和调用方法。
        """
        if isinstance(node, ast.Call):
            callable_method = self._execute_codegen_node(node.func, scope)
            args = [self._evaluate_safe_ast_value(arg, {"re": re}) for arg in node.args]
            kwargs = {
                kw.arg: self._evaluate_safe_ast_value(kw.value, {"re": re})
                for kw in node.keywords
            }
            return callable_method(*args, **kwargs)
        elif isinstance(node, ast.Attribute):
            parent_object = self._execute_codegen_node(node.value, scope)
            return getattr(parent_object, node.attr)
        elif isinstance(node, ast.Name):
            if node.id in scope:
                return scope[node.id]
            raise NameError(f"在codegen的安全作用域中找不到名字: '{node.id}'")
        else:
            raise TypeError(f"不支持的Codegen AST节点类型: {type(node)}")
 
    def _execute_safe_codegen(self, code_str: str, page_obj: Page) -> Locator:
        """
        [内部] 使用AST解释器安全地执行Codegen字符串。
        确保只在给定的page对象上执行，防止不安全代码。
        支持智能化的页面前缀处理，自动修复错误的前缀格式。
        """
        try:
            # 智能化Codegen解析：检测并修复页面前缀错误
            processed_code = self._process_codegen_prefix(code_str)
            
            full_code_to_parse = f"page.{processed_code}"
            tree = ast.parse(full_code_to_parse, mode='eval')
            safe_scope = {'page': page_obj}
            result = self._execute_codegen_node(tree.body, safe_scope)
            if not isinstance(result, Locator):
                raise TypeError("Codegen链式调用最终未返回一个Locator对象")
            return result
        except Exception as e:
            raise ValueError(f"解析或执行 Codegen 字符串 '{code_str}' 失败: {e}")
    
    def _process_codegen_prefix(self, code_str: str) -> str:
        """
        [内部] 智能化处理Codegen字符串的页面前缀。
        检测并移除错误的页面前缀（如page13.、page1.等），确保正确的前缀格式。
        
        Args:
            code_str: 原始的codegen字符串
            
        Returns:
            处理后的codegen字符串
        """
        if not code_str or not isinstance(code_str, str):
            return code_str
            
        invalid_prefix_match = re.match(r'^(page\d+)\.', code_str)
        if invalid_prefix_match:
            page_name = invalid_prefix_match.group(1)
            error_message = (
                f"无效页面引用: {page_name}。默认严格模式不会自动改写为当前页，请修正数据源中的页面变量。"
            )
            print(f"    [Codegen] {error_message}")
            raise ValueError(error_message)
        
        # 检查是否已经以page.开头，如果是则移除，避免重复前缀
        if code_str.startswith('page.'):
            processed_code = code_str[5:]  # 移除'page.'前缀
            print(f"    [Codegen] 移除重复前缀: {code_str} -> {processed_code}")
            return processed_code
            
        # 正常情况，返回原始字符串
        return code_str
 
    def _get_locator(self, **kwargs) -> Locator:
        """
        [内部] 关键字驱动框架的定位核心。
        根据Excel数据动态选择定位策略（css, xpath, get_by_role, codegen等）
        并从正确的目标页面获取Playwright的Locator对象。
        """
        target_page = self._get_target_page(**kwargs)
        locator_type = str(kwargs.get('定位方式', '')).lower()
        target = kwargs.get('目标对象')
        
        if not locator_type or not target:
            raise ValueError("关键字缺少'定位方式'或'目标对象'")

        if locator_type == 'css':
            return target_page.locator(target)
        if locator_type == 'xpath':
            return target_page.locator(f"xpath={target}")
        if locator_type == 'get_by_text':
            # 处理严格模式违规问题：如果匹配多个元素，使用first()
            try:
                locator = target_page.get_by_text(target)
                # 检查是否匹配多个元素
                count = locator.count()
                if count > 1:
                    print(f"    [定位器] get_by_text('{target}') 匹配到{count}个元素，使用第一个")
                    return locator.first()
                return locator
            except Exception as e:
                # 如果出现严格模式违规，直接使用first()
                if "strict mode violation" in str(e).lower():
                    print(f"    [定位器] get_by_text('{target}') 严格模式违规，使用第一个元素")
                    return target_page.get_by_text(target).first()
                else:
                    raise e
        if locator_type == 'get_by_label':
            return target_page.get_by_label(target)
        if locator_type == 'get_by_placeholder':
            return target_page.get_by_placeholder(target)
        if locator_type == 'get_by_role':
            combined_args_str = target
            data_content = str(kwargs.get('数据内容', ''))
            if data_content and re.search(r'^\s*\w+\s*=', data_content):
                if not combined_args_str.endswith(','):
                    combined_args_str += ','
                combined_args_str += data_content
            modifier_match = re.search(r'(\.(?:first|last|nth\(\d+\)|filter\([^)]+\)))$', combined_args_str)
            core_args_str, modifier_str = (
                combined_args_str[:-len(modifier_match.group(1))].strip(),
                modifier_match.group(1),
            ) if modifier_match else (combined_args_str, "")
            try:
                tree = ast.parse(f"f({core_args_str})")
                call_node = tree.body[0].value
                args = [
                    self._evaluate_safe_ast_value(arg, {"re": re})
                    for arg in call_node.args
                ]
                kwargs_dict = {
                    kw.arg: self._evaluate_safe_ast_value(kw.value, {"re": re})
                    for kw in call_node.keywords
                }
                base_locator = target_page.get_by_role(*args, **kwargs_dict)
                if not modifier_str:
                    return base_locator

                modifier_tree = ast.parse(f"base_locator{modifier_str}", mode='eval')
                result = self._execute_codegen_node(
                    modifier_tree.body,
                    {"base_locator": base_locator},
                )
                if not isinstance(result, Locator):
                    raise TypeError("get_by_role 修饰链最终未返回 Locator")
                return result
            except Exception as e:
                raise ValueError(f"解析 get_by_role 参数 '{combined_args_str}' 失败: {e}")
        if locator_type == 'chain':
            parts, scope = [part.strip() for part in target.split('>>')], target_page
            for part in parts:
                if not part: raise ValueError(f"链式定位器 '{target}' 中包含空部分")
                scope = scope.locator(part)
            return scope
        if locator_type == 'codegen':
            return self._execute_safe_codegen(target, target_page)
        
        raise ValueError(f"不支持的定位方式: '{locator_type}'")

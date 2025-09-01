# -*- coding: utf-8 -*-
"""
验证断言模块
提供测试验证和断言相关的关键字
"""

import re
import time
import pytest
from playwright.sync_api import Error as PlaywrightTimeoutError, expect
from .base import _log_action


class VerificationMixin:
    """验证断言Mixin类
     
    提供测试验证和断言相关的方法实现。
    """
    
    def expect_codegen(self, **kwargs):
        """
        [关键字] 执行一个完整的、从Inspector复制的Playwright expect断言表达式。
        提供了极高的灵活性来处理复杂断言。
        
        目标对象: 形如 'expect(page.locator("...")).to_have_text("...")' 的字符串。
                  可用变量: page, pages (页面列表), page0, page1, page2, ... (页面对象), expect, re。
                   
        增强功能:
        1. 智能页面变量映射 - 自动检测和处理不存在的页面变量
        2. 表达式预解析 - 提取和验证页面变量引用
        3. 错误恢复机制 - 针对页面状态异常的智能处理
        4. 详细日志 - 提供完整的执行过程和错误信息
        """
        expression = kwargs.get('目标对象')
        description = kwargs.get('描述', '执行Codegen断言')
        
        if not expression:
            pytest.fail(f"✗ [{description}] 失败: 缺少目标对象表达式")
        
        print(f"执行 [{description}]: {expression}")
        
        # 1. 表达式预解析 - 提取页面变量引用
        referenced_pages = self._extract_page_variables(expression)
        print(f"  [表达式解析] 检测到页面变量: {referenced_pages}")
        
        # 2. 构建智能安全执行作用域
        safe_scope = self._build_enhanced_scope(referenced_pages)
        
        # 3. 验证和准备页面状态
        self._prepare_pages_for_assertion(referenced_pages)
        
        # 4. 执行断言并处理错误
        max_retries = 3
        for attempt in range(max_retries):
            try:
                print(f"  [断言执行] 尝试次数: {attempt + 1}/{max_retries}")
                
                # 执行断言表达式
                eval(expression, safe_scope)
                print(f"✓ [{description}] 断言通过")
                return  # 成功后直接返回
                
            except NameError as e:
                error_msg = str(e)
                if "is not defined" in error_msg:
                    missing_var = self._extract_missing_variable(error_msg)
                    if missing_var and missing_var.startswith('page'):
                        print(f"  [错误处理] 检测到缺失页面变量: {missing_var}")
                        
                        # 尝试恢复缺失的页面变量
                        if self._recover_missing_page_variable(missing_var, safe_scope):
                            print(f"  [错误恢复] 成功恢复页面变量: {missing_var}")
                            continue  # 重试执行
                        else:
                            self._handle_unrecoverable_error(description, e, expression, safe_scope)
                            return
                    else:
                        pytest.fail(f"✗ [{description}] 变量错误: {e}")
                else:
                    pytest.fail(f"✗ [{description}] 名称错误: {e}")
                    
            except (PlaywrightTimeoutError, AssertionError) as e:
                # 页面状态或断言失败，尝试恢复
                if attempt < max_retries - 1:
                    print(f"  [错误处理] 断言失败，尝试恢复页面状态: {e}")
                    if self._recover_pages_state(referenced_pages):
                        print(f"  [错误恢复] 页面状态恢复成功，重试断言")
                        time.sleep(1)  # 等待页面稳定
                        continue
                    else:
                        print(f"  [错误恢复] 页面状态恢复失败")
                
                pytest.fail(f"✗ [{description}] 失败: {e}")
                
            except Exception as e:
                # 其他未知错误
                if attempt < max_retries - 1:
                    print(f"  [错误处理] 未知错误，尝试恢复: {e}")
                    time.sleep(0.5)
                    continue
                
                self._handle_unrecoverable_error(description, e, expression, safe_scope)
                return
        
        # 所有重试都失败
        pytest.fail(f"✗ [{description}] 执行失败: 超过最大重试次数 ({max_retries})")
    
    def _extract_page_variables(self, expression: str) -> list:
        """
        [内部] 从表达式中提取所有页面变量引用。
        支持 page, page0, page1, page2, ... pageN 等变量模式。
        """
        import re
        # 匹配 page 后跟数字或者单独的 page
        page_pattern = r'\bpage(?:\d+)?\b'
        matches = re.findall(page_pattern, expression)
        return list(set(matches))  # 去重
    
    def _build_enhanced_scope(self, referenced_pages: list) -> dict:
        """
        [内部] 构建增强的安全执行作用域。
        包含基础变量和智能页面变量映射。
        """
        # 基础作用域
        safe_scope = {
            "expect": self.expect,
            "re": re,
            "__builtins__": {}  # 限制内置函数访问
        }
        
        current_pages = self.context.pages
        current_count = len(current_pages)
        
        print(f"  [作用域构建] 当前页面数量: {current_count}, 引用页面: {referenced_pages}")
        
        # 添加兼容性页面变量
        if current_count > 0:
            safe_scope["page"] = current_pages[0]  # 主页面
            safe_scope["page0"] = current_pages[0]  # 兼容性
        safe_scope["pages"] = current_pages  # 页面列表
        
        # 动态添加页面变量 (page1, page2, ...)
        for i in range(current_count):
            safe_scope[f"page{i+1}"] = current_pages[i]
        
        # 为不存在的页面变量提供占位符或错误处理
        for page_var in referenced_pages:
            if page_var not in safe_scope:
                if page_var == "page" and current_count > 0:
                    safe_scope["page"] = current_pages[0]
                elif page_var.startswith("page") and len(page_var) > 4:
                    # 提取数字部分
                    try:
                        page_num = int(page_var[4:])  # page1 -> 1
                        page_index = page_num - 1     # 1 -> 0
                        if 0 <= page_index < current_count:
                            safe_scope[page_var] = current_pages[page_index]
                        else:
                            print(f"  [作用域构建] ⚠ 页面变量 {page_var} 引用的页面不存在 (索引: {page_index})")
                            # 暂时不添加，让后续处理
                    except ValueError:
                        print(f"  [作用域构建] ⚠ 无法解析页面变量: {page_var}")
        
        print(f"  [作用域构建] 已构建页面变量: {[k for k in safe_scope.keys() if k.startswith('page')]}")
        return safe_scope
    
    def _prepare_pages_for_assertion(self, referenced_pages: list):
        """
        [内部] 为断言执行准备和验证页面状态。
        确保引用的页面处于可用状态。
        """
        current_count = len(self.context.pages)
        print(f"  [页面准备] 验证 {len(referenced_pages)} 个页面变量的状态")
        
        for page_var in referenced_pages:
            if page_var == "page" or page_var == "page0":
                if current_count > 0:
                    page = self.context.pages[0]
                    if not self._validate_page_state(page, "主页面"):
                        self._recover_page_state(page)
            elif page_var.startswith("page") and len(page_var) > 4:
                try:
                    page_num = int(page_var[4:])
                    page_index = page_num - 1
                    if 0 <= page_index < current_count:
                        page = self.context.pages[page_index]
                        if not self._validate_page_state(page, f"页面{page_num}"):
                            self._recover_page_state(page)
                    else:
                        print(f"  [页面准备] ⚠ {page_var} 对应的页面不存在")
                except ValueError:
                    print(f"  [页面准备] ⚠ 无法解析页面变量: {page_var}")
    
    def _extract_missing_variable(self, error_message: str) -> str:
        """
        [内部] 从 NameError 错误消息中提取缺失的变量名。
        """
        import re
        # 匹配 "name 'xxx' is not defined" 格式
        match = re.search(r"name '([^']+)' is not defined", error_message)
        return match.group(1) if match else None
    
    def _recover_missing_page_variable(self, missing_var: str, safe_scope: dict) -> bool:
        """
        [内部] 尝试恢复缺失的页面变量。
        对于页面已关闭或不存在的情况，提供合理的替代方案。
        """
        print(f"    [变量恢复] 尝试恢复页面变量: {missing_var}")
        
        if missing_var == "page":
            # 主页面变量
            if len(self.context.pages) > 0:
                safe_scope["page"] = self.context.pages[0]
                print(f"    [变量恢复] ✓ 恢复主页面变量 'page'")
                return True
        elif missing_var.startswith("page"):
            try:
                # 解析页面编号
                page_num = int(missing_var[4:]) if len(missing_var) > 4 else 0
                page_index = page_num - 1 if page_num > 0 else 0
                
                current_count = len(self.context.pages)
                if page_index < current_count:
                    # 页面存在，直接映射
                    safe_scope[missing_var] = self.context.pages[page_index]
                    print(f"    [变量恢复] ✓ 映射 '{missing_var}' 到现有页面 (索引: {page_index})")
                    return True
                else:
                    # 页面不存在，尝试使用最后一个页面作为替代
                    if current_count > 0:
                        safe_scope[missing_var] = self.context.pages[-1]
                        print(f"    [变量恢复] ⚠ '{missing_var}' 不存在，使用最后页面作为替代")
                        return True
                    else:
                        print(f"    [变量恢复] ✗ 无可用页面来恢复 '{missing_var}'")
                        return False
            except ValueError:
                print(f"    [变量恢复] ✗ 无法解析页面变量: {missing_var}")
                return False
        
        return False
    
    def _recover_pages_state(self, referenced_pages: list) -> bool:
        """
        [内部] 尝试恢复多个页面的状态。
        """
        print(f"    [页面恢复] 尝试恢复 {len(referenced_pages)} 个页面的状态")
        recovery_count = 0
        
        for page_var in referenced_pages:
            if page_var.startswith("page"):
                try:
                    if page_var == "page" or page_var == "page0":
                        page_index = 0
                    else:
                        page_num = int(page_var[4:]) if len(page_var) > 4 else 1
                        page_index = page_num - 1
                    
                    if 0 <= page_index < len(self.context.pages):
                        page = self.context.pages[page_index]
                        if self._recover_page_state(page):
                            recovery_count += 1
                except (ValueError, IndexError):
                    continue
        
        success_rate = recovery_count / len(referenced_pages) if referenced_pages else 1
        print(f"    [页面恢复] 恢复成功率: {recovery_count}/{len(referenced_pages)} ({success_rate:.1%})")
        return success_rate >= 0.5  # 至少50%成功率
    
    def _handle_unrecoverable_error(self, description: str, error: Exception, expression: str, safe_scope: dict):
        """
        [内部] 处理无法恢复的错误，提供详细的调试信息。
        """
        print(f"\n  [错误详情] 无法恢复的错误详情:")
        print(f"    表达式: {expression}")
        print(f"    错误类型: {type(error).__name__}")
        print(f"    错误信息: {error}")
        
        print(f"\n  [作用域状态]:")
        page_vars = {k: v for k, v in safe_scope.items() if k.startswith('page')}
        for var_name, page_obj in page_vars.items():
            try:
                status = "正常" if not page_obj.is_closed() else "已关闭"
                url = page_obj.url if not page_obj.is_closed() else "N/A"
                print(f"    {var_name}: {status} ({url})")
            except:
                print(f"    {var_name}: 异常状态")
        
        print(f"\n  [页面列表]:")
        for i, page in enumerate(self.context.pages):
            try:
                status = "正常" if not page.is_closed() else "已关闭"
                print(f"    页面{i+1}: {status} ({page.url})")
            except:
                print(f"    页面{i+1}: 异常状态")
        
        pytest.fail(f"✗ [{description}] 无法恢复的错误: {error}")
    
    @_log_action
    def verify(self, **kwargs):
        """
        [关键字] 通用验证中心，使用Playwright的expect断言。
        验证类型:
            - element_visible
            - element_text_equals
            - element_text_contains
            - url_contains
        """
        verify_type = str(kwargs.get('验证类型', '')).lower()
        description = kwargs.get('描述', verify_type)
        print(f"执行验证 [{description}]")
        target_page = self._get_target_page(**kwargs) # URL验证作用于页面
        try:
            if 'element' in verify_type:
                locator = self._get_locator(**kwargs)
                if verify_type == 'element_visible':
                    self.expect(locator).to_be_visible()
                elif verify_type == 'element_text_equals':
                    self.expect(locator).to_have_text(str(kwargs.get('数据内容', '')))
                elif verify_type == 'element_text_contains':
                    self.expect(locator).to_contain_text(str(kwargs.get('数据内容', '')))
                else:
                    pytest.fail(f"不支持的元素验证类型: '{verify_type}'")
            elif verify_type == 'url_contains':
                self.expect(target_page).to_have_url(re.compile(f".*{re.escape(str(kwargs.get('数据内容', '')))}.*"))
            else:
                pytest.fail(f"不支持的验证类型: '{verify_type}'")
            print(f"✓ 验证通过: [{description}]")
        except (PlaywrightTimeoutError, AssertionError) as e:
             pytest.fail(f"✗ 验证失败: {description} - {e}")
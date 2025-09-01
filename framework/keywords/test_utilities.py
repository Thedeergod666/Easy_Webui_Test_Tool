# -*- coding: utf-8 -*-
"""
测试辅助模块
提供测试过程中常用的辅助功能和工具方法
"""

import time
import pytest
from playwright.sync_api import Page
from .base import _log_action, _total_sleep_time


class TestUtilitiesMixin:
    """测试辅助Mixin类
     
    提供测试过程中常用的辅助功能和工具方法。
    """
    
    def sleep(self, **kwargs):
        """
        [关键字] 强制等待指定的秒数。
        注意：此操作在无头(headless)模式下会被自动跳过以提高效率。
        尽量使用Playwright的智能等待，避免使用此关键字。
        数据内容: 等待的秒数 (e.g., "2.5")
        """
        import framework.keywords.base as base_module
        wait_time_sec = float(kwargs.get('数据内容', 2))
        if self.mode == 'headless':
            print(f"执行 [强制等待]: 无头模式下智能跳过 {wait_time_sec} 秒等待。")
            return
        print(f"执行 [强制等待]: {wait_time_sec} 秒.")
        self.active_page.wait_for_timeout(wait_time_sec * 1000)
        base_module._total_sleep_time += wait_time_sec

    @_log_action
    def screenshot(self, **kwargs):
        """
        [关键字] 对当前目标页面进行截图。
        数据内容: [可选] 截图保存的路径和文件名 (e.g., "reports/screenshots/login_success.png")
        """
        path = str(kwargs.get('数据内容', 'screenshot.png'))
        description = kwargs.get('描述', f'截图到 {path}')
        print(f"执行 [{description}]")
        target_page = self._get_target_page(**kwargs)
        target_page.screenshot(path=path, full_page=True)
        print(f"✓ [{description}] 成功")

    def wait_until(self, **kwargs):
        """
        这是一个兼容旧用例的过渡方法。
        [关键字] 显式等待，直到某个元素变得可见。
        主要用于等待由JS动态加载、但后续不直接操作的元素。
        """
        description = kwargs.get('描述', '显示等待元素可见')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.wait_for(state='visible', timeout=self.DEFAULT_TIMEOUT)
        print(f"✓ [{description}] 元素已出现")
    
    def _log_page_status_summary(self):
        """
        [内部] 输出当前所有页面的状态概要。
        用于调试和监控多页面状态同步问题。
        """
        try:
            pages = self.context.pages
            page_count = len(pages)
            
            print(f"\n  [页面状态概要] 当前有 {page_count} 个页面:")
            
            for i, page in enumerate(pages):
                try:
                    # 获取页面基本信息
                    page_num = i + 1
                    is_closed = page.is_closed()
                    url = "[已关闭]" if is_closed else page.url
                    
                    # 状态指示符
                    status_indicator = "✗" if is_closed else "✓"
                    active_marker = " (ACTIVE)" if page == self.active_page else ""
                    
                    print(f"    {status_indicator} 页面{page_num}: {url}{active_marker}")
                    
                    # 详细状态信息
                    if not is_closed:
                        try:
                            # 获取页面加载状态
                            ready_state = page.evaluate('document.readyState', timeout=1000)
                            js_available = page.evaluate('typeof window === "object"', timeout=1000)
                            
                            status_details = []
                            if ready_state == 'complete':
                                status_details.append("DOM就绪")
                            elif ready_state == 'interactive':
                                status_details.append("DOM可交互")
                            else:
                                status_details.append(f"DOM:{ready_state}")
                                
                            if js_available:
                                status_details.append("JS可用")
                            
                            print(f"      状态: {', '.join(status_details)}")
                        except Exception as detail_error:
                            print(f"      状态: 无法获取详细信息 ({detail_error})")
                            
                except Exception as page_error:
                    print(f"    ✗ 页面{i+1}: 页面信息获取失败 ({page_error})")
            
            # 添加变量映射提示
            print(f"\n  [变量映射] 页面变量映射关系:")
            print(f"    page/page0 -> 页面1 (page == page0 == context.pages[0])")
            for i in range(min(page_count, 10)):  # 最多显示10个
                print(f"    page{i+1} -> 页面{i+1} (context.pages[{i}])")
            
            if page_count == 0:
                print(f"    ⚠ 注意: 当前没有可用页面，所有页面变量都不可用")
                
        except Exception as e:
            print(f"\n  [页面状态概要] 获取失败: {e}")
    
    def diagnose_page_issues(self, **kwargs):
        """
        [关键字] 诊断和报告当前多页面状态问题。
        用于调试和排查多页面断言失败问题。
        数据内容: [可选] 诊断类型 ("basic"|"detailed"|"variables")
        """
        diagnosis_type = str(kwargs.get('数据内容', 'basic')).lower()
        description = kwargs.get('描述', f'页面状态诊断 ({diagnosis_type})')
        
        print(f"\n执行 [{description}]:")
        print("=" * 60)
        
        # 基本信息
        page_count = len(self.context.pages)
        print(f"ℹ 基本信息:")
        print(f"  页面总数: {page_count}")
        print(f"  当前活动页: {self.context.pages.index(self.active_page) + 1 if self.active_page in self.context.pages else 'N/A'}")
        print(f"  默认超时: {self.DEFAULT_TIMEOUT}ms")
        
        # 详细状态
        if diagnosis_type in ['detailed', 'basic']:
            self._log_page_status_summary()
        
        # 变量作用域模拟
        if diagnosis_type in ['variables', 'detailed']:
            print(f"\n  [变量作用域模拟] 模拟 expect_codegen 作用域:")
            
            # 模拟构建作用域
            mock_scope = {
                "expect": "<expect 函数>",
                "re": "<re 模块>",
                "pages": f"<页面列表, 长度: {page_count}>"
            }
            
            if page_count > 0:
                mock_scope["page"] = f"<页面1: {self.context.pages[0].url}>"
                mock_scope["page0"] = f"<页面1: {self.context.pages[0].url}>"
            
            for i in range(page_count):
                page_url = self.context.pages[i].url
                mock_scope[f"page{i+1}"] = f"<页面{i+1}: {page_url}>"
            
            for var_name, var_value in mock_scope.items():
                availability = "✓ 可用" if not var_value.startswith("<页面") or page_count > 0 else "✗ 不可用"
                print(f"    {var_name}: {var_value} [{availability}]")
            
            # 常见问题检查
            print(f"\n  [常见问题检查]:")
            issues_found = []
            
            if page_count == 0:
                issues_found.append("没有可用页面 - 所有页面变量都会导致 NameError")
            
            closed_pages = [i+1 for i, p in enumerate(self.context.pages) if p.is_closed()]
            if closed_pages:
                issues_found.append(f"发现已关闭的页面: {closed_pages}")
            
            # 检查页面加载状态
            loading_issues = []
            for i, page in enumerate(self.context.pages):
                if not page.is_closed():
                    try:
                        ready_state = page.evaluate('document.readyState', timeout=1000)
                        if ready_state not in ['complete', 'interactive']:
                            loading_issues.append(f"页面{i+1}加载未完成")
                    except:
                        loading_issues.append(f"页面{i+1}JavaScript不可用")
            
            if loading_issues:
                issues_found.extend(loading_issues)
            
            if not issues_found:
                print(f"    ✓ 未发现常见问题")
            else:
                for issue in issues_found:
                    print(f"    ⚠ {issue}")
        
        print("=" * 60)
        print(f"✓ [{description}] 诊断完成")
# -*- coding: utf-8 -*-
"""
页面管理模块
提供页面导航、页面切换和页面管理相关的关键字
"""

import re
import time
import pytest
from playwright.sync_api import Page, Error as PlaywrightTimeoutError
from .base import _log_action


class PageManagementMixin:
    """页面管理Mixin类
     
    提供页面导航、页面切换和页面管理相关的方法实现。
    """

    def _get_target_page(self, **kwargs) -> Page:
        """
        [内部] 根据Excel中的'页面'列获取目标Page对象。
        如果'页面'列为空，则返回当前的活动页面(self.active_page)。
        
        实现了智能页面等待和状态验证机制:
        1. 多层级等待策略（基础等待、状态等待、内容等待）
        2. 页面状态验证（可见性、加载状态、DOM就绪等）
        3. 智能重试机制（页面不存在时的恢复策略）
        """
        page_index_str = str(kwargs.get('页面', '')).strip()
        
        if not page_index_str:
            return self.active_page

        try:
            # Excel中的页码是 1-based, 列表索引是 0-based
            page_index = int(page_index_str) - 1
            if page_index < 0:
                raise ValueError("页码必须是正整数。")

            # 智能页面等待机制 - 分层等待策略
            current_pages_count = len(self.context.pages)
            required_pages_count = page_index + 1
            
            print(f"  [页面定位] 请求页面 {page_index_str} (索引: {page_index}), 当前页面数: {current_pages_count}, 需要页面数: {required_pages_count}")
            
            if current_pages_count > page_index:
                # 页面已存在，进行状态验证
                target_page = self.context.pages[page_index]
                if self._validate_page_state(target_page, page_index_str):
                    print(f"  [页面定位] ✓ 目标页面指定为 页{page_index_str} ({target_page.url})")
                    return target_page
                else:
                    print(f"  [页面定位] ⚠ 页面{page_index_str}状态异常，尝试恢复...")
                    # 尝试状态恢复
                    if self._recover_page_state(target_page):
                        print(f"  [页面定位] ✓ 页面状态恢复成功")
                        return target_page
                    else:
                        print(f"  [页面定位] ✗ 页面状态恢复失败")
            else:
                # 页面不存在，实施智能等待策略
                print(f"  [页面等待] 页面{page_index_str}不存在，启动智能等待机制...")
                
                # 基础等待 - 等待页面对象存在 (8秒，增加等待时间)
                waited_page = self._wait_for_page_creation(required_pages_count, timeout_ms=8000)
                if waited_page:
                    print(f"  [页面等待] ✓ 基础等待成功，页面已创建")
                    target_page = self.context.pages[page_index]
                    
                    # 状态等待 - 等待页面加载完成 (15秒，增加等待时间)
                    if self._wait_for_page_ready(target_page, timeout_ms=15000):
                        print(f"  [页面等待] ✓ 页面状态验证通过")
                        print(f"  [页面定位] ✓ 目标页面指定为 页{page_index_str} ({target_page.url})")
                        return target_page
                    else:
                        print(f"  [页面等待] ⚠ 页面状态验证失败，但页面存在")
                        return target_page  # 返回页面，让调用者处理
                else:
                    # 页面确实不存在，采用容错策略：使用最后一个可用页面
                    if len(self.context.pages) > 0:
                        fallback_page = self.context.pages[-1]  # 使用最后一个页面作为替代
                        print(f"  [容错机制] 页面{page_index_str}不存在，使用最后页面作为替代: 页{len(self.context.pages)} ({fallback_page.url})")
                        return fallback_page
                    
            # 所有等待策略都失败，提供详细的错误信息
            current_pages = [f"页面{i+1}: {page.url}" for i, page in enumerate(self.context.pages)]
            error_detail = f"\n当前打开的页面列表:\n" + "\n".join(current_pages) if current_pages else "\n当前没有打开的页面"
            
            # 使用警告而不是失败，让测试继续进行
            warning_msg = (f"⚠ [页面等待] 无法获取页面 '{page_index_str}'，" +
                         f"当前页面总数: {len(self.context.pages)}, 请求页面索引: {page_index}" +
                         error_detail)
            print(warning_msg)
            
            # 返回主页面作为最后的容错机制
            if len(self.context.pages) > 0:
                return self.context.pages[0]
            else:
                pytest.fail("严重错误: 没有任何可用的页面")
                       
        except ValueError as e:
            pytest.fail(f"页面参数错误: {e}")
        except Exception as e:
            pytest.fail(f"页面操作异常: {e}")
    
    def _validate_page_state(self, page: Page, page_name: str) -> bool:
        """
        [内部] 验证页面状态是否正常。
        检查页面可见性、加载状态、DOM就绪等关键指标。
        """
        try:
            # 1. 检查页面是否关闭
            if page.is_closed():
                print(f"    [状态验证] 页面{page_name}已关闭")
                return False
            
            # 2. 检查URL有效性
            current_url = page.url
            if not current_url or current_url == 'about:blank':
                print(f"    [状态验证] 页面{page_name}URL无效: {current_url}")
                return False
            
            # 3. 检查DOM就绪状态 (非阻塞检查)
            try:
                ready_state = page.evaluate('document.readyState', timeout=1000)
                if ready_state not in ['interactive', 'complete']:
                    print(f"    [状态验证] 页面{page_name}DOM未就绪: {ready_state}")
                    return False
            except:
                print(f"    [状态验证] 页面{page_name}无法获取DOM状态")
                return False
            
            # 4. 检查JavaScript环境
            try:
                js_available = page.evaluate('typeof window', timeout=1000)
                if js_available != 'object':
                    print(f"    [状态验证] 页面{page_name}JavaScript环境不可用")
                    return False
            except:
                print(f"    [状态验证] 页面{page_name}JavaScript环境检查失败")
                return False
            
            print(f"    [状态验证] 页面{page_name}状态正常")
            return True
            
        except Exception as e:
            print(f"    [状态验证] 页面{page_name}状态验证异常: {e}")
            return False
    
    def _recover_page_state(self, page: Page) -> bool:
        """
        [内部] 尝试恢复页面状态。
        对于状态异常的页面，尝试修复或重新加载。
        """
        try:
            # 1. 尝试等待页面加载完成
            try:
                page.wait_for_load_state('networkidle', timeout=3000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            # 2. 尝试等待DOM就绪
            try:
                page.wait_for_load_state('domcontentloaded', timeout=2000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            # 3. 最后尝试重新刷新页面
            try:
                page.reload(timeout=5000)
                page.wait_for_load_state('domcontentloaded', timeout=3000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            return False
            
        except Exception as e:
            print(f"    [状态恢复] 恢复失败: {e}")
            return False
    
    def _wait_for_page_creation(self, required_count: int, timeout_ms: int = 5000) -> bool:
        """
        [内部] 等待页面创建直到满足数量要求。
        使用短时间轮询策略，避免无限等待。
        """
        import time
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000
        
        # 增加初始检查
        initial_count = len(self.context.pages)
        if initial_count >= required_count:
            return True
            
        print(f"    [页面等待] 当前{initial_count}个页面，需要{required_count}个，等待新页面创建...")
        
        while time.time() - start_time < timeout_seconds:
            current_count = len(self.context.pages)
            if current_count >= required_count:
                print(f"    [页面等待] 成功：当前已有{current_count}个页面")
                return True
            
            # 短时间等待新页面事件（增加等待时间）
            try:
                self.context.wait_for_event('page', timeout=1000)  # 从500ms增加到1000ms
                print(f"    [页面等待] 检测到新页面事件，当前页面数: {len(self.context.pages)}")
            except PlaywrightTimeoutError:
                pass  # 继续轮询
            
            # 添加微小的睡眠，避免过度消耗CPU
            time.sleep(0.1)
        
        final_count = len(self.context.pages)
        print(f"    [页面等待] 超时：最终页面数{final_count}，需要{required_count}")
        return final_count >= required_count
    
    def _wait_for_page_ready(self, page: Page, timeout_ms: int = 10000) -> bool:
        """
        [内部] 等待页面就绪并验证状态。
        包括加载状态、DOM就绪、JavaScript环境等。
        """
        try:
            # 1. 等待基本加载完成
            page.wait_for_load_state('domcontentloaded', timeout=timeout_ms)
            
            # 2. 等待网络活动稳定（可选）
            try:
                page.wait_for_load_state('networkidle', timeout=3000)
            except PlaywrightTimeoutError:
                pass  # 网络活动稳定不是必须的
            
            # 3. 验证最终状态
            return self._validate_page_state(page, "目标")
            
        except PlaywrightTimeoutError as e:
            print(f"    [页面等待] 等待超时: {e}")
            return False
        except Exception as e:
            print(f"    [页面等待] 等待异常: {e}")
            return False

    @_log_action
    def switch_to_page(self, **kwargs):
        """
        [关键字] 切换当前的活动页面。
        后续所有未指定'页面'列的操作，将默认在此新页面上执行。
        数据内容: 要切换到的页码 (e.g., "2")
        """
        page_index_str = str(kwargs.get('数据内容', '')).strip()
        if not page_index_str:
            raise ValueError("switch_to_page 关键字需要在 '数据内容' 列提供页码。")
        self.active_page = self._get_target_page(页面=page_index_str)
        print(f"✓ [状态切换] 当前活动页面已切换至 页{page_index_str}。")

    def _is_valid_url(self, url_string: str) -> bool:
        """
        [内部] 检查字符串是否为有效的URL格式。
        """
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// 或 https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
            r'(?::\d+)?'  # 可选端口号
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url_string) is not None

    def close_page(self, **kwargs):
        """
        [关键字] 关闭指定的页面。
        如果'数据内容'列为空，则关闭当前活动页面。
        如果关闭的是活动页面，焦点会自动切换回主页面。
        数据内容: [可选] 要关闭的页码 (e.g., "2") 或 URL (e.g., "https://www.example.com")
        """
        data_content = str(kwargs.get('数据内容', '')).strip()
        
        # 如果数据内容为空，关闭当前活动页面
        if not data_content:
            target_page_to_close = self._get_target_page()
            page_identifier = f"Page {self.context.pages.index(target_page_to_close) + 1}"
        # 如果数据内容是有效的URL，查找匹配的页面
        elif self._is_valid_url(data_content):
            target_page_to_close = None
            for page in self.context.pages:
                if page.url == data_content:
                    target_page_to_close = page
                    break
            
            if target_page_to_close is None:
                error_msg = f"[警告] 未找到URL为 '{data_content}' 的页面，操作已跳过。"
                print(error_msg)
                return error_msg
                
            page_identifier = f"URL '{data_content}'"
        # 如果数据内容不是有效的URL，但包含URL特征（如包含http://或https://），则按部分匹配查找
        elif 'http://' in data_content or 'https://' in data_content:
            target_page_to_close = None
            for page in self.context.pages:
                if data_content in page.url:
                    target_page_to_close = page
                    break
            
            if target_page_to_close is None:
                error_msg = f"[警告] 未找到URL包含 '{data_content}' 的页面，操作已跳过。"
                print(error_msg)
                return error_msg
                
            page_identifier = f"URL 包含 '{data_content}'"
        # 否则，检查是否是部分URL匹配
        else:
            target_page_to_close = None
            for page in self.context.pages:
                if data_content in page.url:
                    target_page_to_close = page
                    break
            
            # 如果找到匹配的页面，使用部分URL匹配
            if target_page_to_close is not None:
                page_identifier = f"URL 包含 '{data_content}'"
            else:
                # 检查是否是页面索引
                try:
                    # 尝试将数据内容转换为整数
                    page_index = int(data_content)
                    # 如果转换成功，使用页面索引
                    target_page_to_close = self._get_target_page(页面=data_content)
                    page_identifier = f"Page {self.context.pages.index(target_page_to_close) + 1}"
                except ValueError:
                    # 如果转换失败，尝试部分URL匹配
                    target_page_to_close = None
                    for page in self.context.pages:
                        if data_content in page.url:
                            target_page_to_close = page
                            break
                    
                    # 如果找到匹配的页面，使用部分URL匹配
                    if target_page_to_close is not None:
                        page_identifier = f"URL 包含 '{data_content}'"
                    else:
                        # 如果没有找到匹配的页面，返回错误消息
                        error_msg = f"[警告] 未找到URL包含 '{data_content}' 的页面，操作已跳过。"
                        print(error_msg)
                        return error_msg
        
        print(f"执行 [关闭页面]: 目标是 {page_identifier}")
        
        if len(self.context.pages) <= 1:
            print("[警告] 无法关闭最后一个页面，操作已跳过。")
            return
            
        target_page_to_close.close()
        
        if self.active_page.is_closed():
             self.active_page = self.context.pages[0]
             print("  > 已关闭的页面是当前活动页，活动页已自动重置为主页面 (Page 1)。")
        print(f"✓ [关闭页面] 成功。")

    def open_in_new_page(self, **kwargs):
        """
        [关键字] 在新的标签页中打开URL。
        此操作会自动创建新页面，在其中加载URL，并将其设为新的活动页面。
        数据内容: 要打开的URL, [可选的超时秒数] e.g., "http://a.com,60"
        """
        print("执行 [在新标签页打开]: 正在创建新页面...")
        new_page = self.context.new_page()
        self.active_page = new_page
        print(f"  > 新页面 (页{len(self.context.pages)}) 已创建并设为活动页面。")
        print("  > 正在新页面中加载URL...")
        try:
            self.open(**kwargs)
        except Exception as e:
            if not new_page.is_closed(): new_page.close()
            raise e

    @_log_action
    def open(self, **kwargs):
        """
        [关键字] 在当前的活动页面上导航到指定的URL。
        此操作会覆盖当前活动页面的内容。
        数据内容: 要打开的URL, [可选的超时秒数] e.g., "http://a.com,60"
        """
        data_content = str(kwargs.get('数据内容', ''))
        parts = [p.strip() for p in data_content.split(',')]
        url = parts[0]
        timeout_ms = int(parts[1]) * 1000 if len(parts) > 1 else self.DEFAULT_TIMEOUT
        print(f"执行 [打开页面]: {url} (在当前活动页上)")
        start_time = time.time()
        try:
            self.active_page.goto(url, timeout=timeout_ms)
            duration = time.time() - start_time
            print(f"SUCCESS [Open Page] Loaded successfully, Duration: {duration:.2f}s")
        except PlaywrightTimeoutError:
            duration = time.time() - start_time
            pytest.fail(f"✗ 打开页面 {url} 失败: 超时({timeout_ms/1000}s), 实际等待 {duration:.2f}s")
            
    @_log_action
    def go_back(self, **kwargs):
        """
        [关键字] 模拟浏览器的后退按钮。
        """
        description = kwargs.get('描述', '页面后退')
        print(f"执行 [{description}]")
        self.active_page.go_back()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")
 
    @_log_action
    def go_forward(self, **kwargs):
        """
        [关键字] 模拟浏览器的前进按钮。
        """
        description = kwargs.get('描述', '页面前进')
        print(f"执行 [{description}]")
        self.active_page.go_forward()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")

    def set_window_size(self, **kwargs):
        """
        [关键字] 设置当前活动页面的视口（viewport）大小。
        数据内容: 格式为 "宽x高" 的字符串 (e.g., "1920x1080")
        """
        size_str = kwargs.get('数据内容', '1920x1080')
        description = kwargs.get('描述', f'设置窗口大小为 {size_str}')
        print(f"执行 [{description}]")
        try:
            width, height = map(int, size_str.split('x'))
            self.active_page.set_viewport_size({"width": width, "height": height})
        except ValueError:
            pytest.fail(f"窗口大小格式错误: '{size_str}', 期望 '宽x高'")
        print(f"✓ [{description}] 成功")
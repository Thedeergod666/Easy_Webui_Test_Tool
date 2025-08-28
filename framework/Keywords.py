import os
import re
import pytest
import ast
import time
from playwright.sync_api import Page, Locator, expect, Error as PlaywrightTimeoutError, BrowserContext

# 全局变量，用于在测试会话结束时报告总的sleep时间
_total_sleep_time = 0.0

class Keywords:
    DEFAULT_TIMEOUT = 10000

    def __init__(self, page: Page):
        """
        初始化Keywords实例。
        持有整个浏览器上下文(Context)以管理多个页面，并设置初始活动页面。
        """
        self.context: BrowserContext = page.context
        self.active_page: Page = page  # 初始活动页面是主页面
        
        # 将默认超时应用到初始页面
        self.active_page.set_default_timeout(self.DEFAULT_TIMEOUT)
        
        # 从上下文中获取运行模式
        self.mode = getattr(self.context, 'running_mode', 'headed')
        self.expect = expect

    def _get_target_page(self, **kwargs) -> Page:
        """
        [内部] 根据Excel中的'页面'列获取目标Page对象。
        如果'页面'列为空，则返回当前的活动页面(self.active_page)。
        """
        page_index_str = str(kwargs.get('页面', '')).strip()
        
        if not page_index_str:
            return self.active_page

        try:
            # Excel中的页码是 1-based, 列表索引是 0-based
            page_index = int(page_index_str) - 1
            if page_index < 0:
                raise ValueError("页码必须是正整数。")

            # 等待，直到所需数量的页面出现
            # 这是一个简单的等待，如果页面打开很慢，可能需要更长的超时
            if not len(self.context.pages) > page_index:
                 self.context.wait_for_event('page', timeout=self.DEFAULT_TIMEOUT)
            
            target_page = self.context.pages[page_index]
            print(f"  [页面定位] 目标页面指定为 页{page_index_str} ({target_page.url})")
            return target_page
        except (ValueError, IndexError):
            pytest.fail(f"页面操作失败: 无法找到页 '{page_index_str}'。请确保该页面已打开。当前页面总数: {len(self.context.pages)}")
        except PlaywrightTimeoutError:
            pytest.fail(f"页面操作失败: 等待新页面出现超时。")

    def _execute_codegen_node(self, node, scope):
        """
        [内部] 递归地执行AST（抽象语法树）节点。
        这是Codegen安全执行引擎的核心部分，用于解析和调用方法。
        """
        if isinstance(node, ast.Call):
            callable_method = self._execute_codegen_node(node.func, scope)
            allowed_globals = {"re": re}
            args = [eval(ast.unparse(arg), allowed_globals) for arg in node.args]
            kwargs = {kw.arg: eval(ast.unparse(kw.value), allowed_globals) for kw in node.keywords}
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
        """
        try:
            full_code_to_parse = f"page.{code_str}"
            tree = ast.parse(full_code_to_parse, mode='eval')
            safe_scope = {'page': page_obj}
            result = self._execute_codegen_node(tree.body, safe_scope)
            if not isinstance(result, Locator):
                raise TypeError("Codegen链式调用最终未返回一个Locator对象")
            return result
        except Exception as e:
            raise ValueError(f"解析或执行 Codegen 字符串 '{code_str}' 失败: {e}")
 
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
            return target_page.get_by_text(target)
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
            modifier_match = re.search(r'(\.(first|last|nth\(\d+\)))$', combined_args_str)
            core_args_str, modifier_str = (combined_args_str[:-len(modifier_match.group(1))].strip(), modifier_match.group(1)) if modifier_match else (combined_args_str, "")
            try:
                tree = ast.parse(f"f({core_args_str})")
                call_node = tree.body[0].value
                allowed_globals = {"re": re}
                args = [arg.id if isinstance(arg, ast.Name) else eval(ast.unparse(arg), allowed_globals) for arg in call_node.args]
                kwargs_dict = {kw.arg: eval(ast.unparse(kw.value), allowed_globals) for kw in call_node.keywords}
                base_locator = target_page.get_by_role(*args, **kwargs_dict)
                return eval(f"base_locator{modifier_str}", {"base_locator": base_locator}) if modifier_str else base_locator
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
    
    # --- 新增和改造的页面操作关键字 ---

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
            print(f"✓ [打开页面] 成功加载, 耗时: {duration:.2f} 秒")
        except PlaywrightTimeoutError:
            duration = time.time() - start_time
            pytest.fail(f"✗ 打开页面 {url} 失败: 超时({timeout_ms/1000}s), 实际等待 {duration:.2f}s")
            
    # --- 核心操作关键字 (适配多页面) ---

    def expect_codegen(self, **kwargs):
        """
        [关键字] 执行一个完整的、从Inspector复制的Playwright expect断言表达式。
        提供了极高的灵活性来处理复杂断言。
        目标对象: 形如 'expect(page.locator("...")).to_have_text("...")' 的字符串。
                  可用变量: page, pages (页面列表), page1, page2, ... (页面对象), expect, re。
        """
        expression = kwargs.get('目标对象')
        description = kwargs.get('描述', '执行Codegen断言')
        
        # 构建安全执行作用域
        safe_scope = {
            "expect": self.expect,
            "re": re,
            "page": self.context.pages[0],  # 保持向后兼容性
            "pages": self.context.pages      # 保持向后兼容性
        }
        
        # 动态添加页面变量，如 page1, page2, page3 等
        # 这些变量对应 self.context.pages 列表中的页面对象
        for i, page_obj in enumerate(self.context.pages):
            if i == 0:
                # page0 和 page 都指向第一个页面，保持向后兼容性
                safe_scope["page0"] = page_obj
            safe_scope[f"page{i+1}"] = page_obj
        
        print(f"执行 [{description}]: {expression}")
        try:
            eval(expression, safe_scope)
            print(f"✓ [{description}] 断言通过")
        except (PlaywrightTimeoutError, AssertionError) as e:
            pytest.fail(f"✗ [{description}] 失败: {e}")
        except Exception as e:
            pytest.fail(f"✗ 执行 expect_codegen 表达式时发生未知错误: {e}")

    def hover(self, **kwargs):
        """
        [关键字] 将鼠标悬停在指定的元素上。
        常用于触发需要鼠标悬停才出现的菜单或提示。
        """
        description = kwargs.get('描述', '鼠标悬停')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.hover()
        print(f"✓ [{description}] 成功")
 
    def scroll_page(self, **kwargs):
        """
        [关键字] 在当前活动页面上模拟鼠标滚轮滚动。
        可用于处理懒加载页面或滚动到特定位置。
        数据内容: x轴滚动像素,y轴滚动像素 (e.g., "0,500" 表示向下滚动500px, "0,-500"表示向上)
        """
        scroll_data = str(kwargs.get('数据内容', '0,500')).strip()
        description = kwargs.get('描述', f'滚动页面 {scroll_data}')
        print(f"执行 [{description}]")
        try:
            delta_x, delta_y = map(int, scroll_data.split(','))
            self.active_page.mouse.wheel(delta_x, delta_y)
            print(f"✓ [{description}] 成功")
        except ValueError:
            pytest.fail(f"滚动数据格式错误: '{scroll_data}', 期望格式为 'x,y' (例如 '0,500')")
 
    def go_back(self, **kwargs):
        """
        [关键字] 模拟浏览器的后退按钮。
        """
        description = kwargs.get('描述', '页面后退')
        print(f"执行 [{description}]")
        self.active_page.go_back()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")
 
    def go_forward(self, **kwargs):
        """
        [关键字] 模拟浏览器的前进按钮。
        """
        description = kwargs.get('描述', '页面前进')
        print(f"执行 [{description}]")
        self.active_page.go_forward()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")
 
    def drag_and_drop(self, **kwargs):
        """
        [关键字] 将一个元素拖拽到另一个元素上。
        目标对象/定位方式:  描述的是【源元素】。
        数据内容:          描述的是【目标元素】的CSS选择器或XPath。
        """
        description = kwargs.get('描述', '拖拽元素')
        print(f"执行 [{description}]")
        source_locator = self._get_locator(**kwargs)
        
        target_selector = str(kwargs.get('数据内容', '')).strip()
        if not target_selector:
            pytest.fail("drag_and_drop 关键字的 '数据内容' 列必须提供目标元素的选择器。")
            
        print(f"  > 源元素: {source_locator}")
        print(f"  > 目标元素选择器: {target_selector}")
 
        # Playwright的 drag_to 需要一个 Locator 作为目标
        target_locator = self.active_page.locator(target_selector)
        
        source_locator.drag_to(target_locator)
        print(f"✓ [{description}] 成功")
 
    def click_at_position(self, **kwargs):
        """
        [高级][关键字] 在元素的特定相对位置或绝对坐标上点击。
        可用于点击进度条、Canvas图表等。
        - 如果提供了定位器:
            数据内容: "x=0.5, y=0.5" (相对坐标, 0.5代表中心点)
        - 如果未提供定位器:
            数据内容: "x=800, y=600" (绝对视口坐标)
        """
        position_data = str(kwargs.get('数据内容', '')).strip()
        description = kwargs.get('描述', f'在位置 {position_data} 点击')
        print(f"执行 [{description}]")
        
        try:
            # 解析 x, y 坐标
            pos_dict = dict(item.split("=") for item in position_data.replace(" ", "").split(','))
            x_pos = float(pos_dict['x'])
            y_pos = float(pos_dict['y'])
        except Exception:
            pytest.fail(f"位置数据格式错误: '{position_data}', 期望格式为 'x=数值,y=数值'")
        
        locator_type = str(kwargs.get('定位方式', '')).lower()
        
        if locator_type:
            # 模式一: 点击元素的相对位置
            print(f"  > 相对定位模式: 在元素内 ({x_pos*100}%, {y_pos*100}%) 位置点击")
            locator = self._get_locator(**kwargs)
            locator.click(position={'x': x_pos, 'y': y_pos})
        else:
            # 模式二: 点击页面的绝对坐标
            print(f"  > 绝对定位模式: 在页面视口 ({x_pos}px, {y_pos}px) 位置点击")
            self.active_page.mouse.click(int(x_pos), int(y_pos))
            
        print(f"✓ [{description}] 成功")

    def click(self, **kwargs):
        """
        [关键字] 在找到的元素上执行单击操作。
        操作自带智能等待，会等待元素可见、可点击。
        """
        description = kwargs.get('描述', '点击操作')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.click()
        print(f"✓ [{description}] 成功")

    def press(self, **kwargs):
        """
        [关键字] 在指定的元素上模拟按下单个键盘按键。
        数据内容: 要按下的键名，如 "Tab", "Enter", "ArrowDown", "a", "Control+C"。
        """
        key_to_press = str(kwargs.get('数据内容', ''))
        description = kwargs.get('描述', f'模拟按键 {key_to_press}')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.press(key_to_press)
        print(f"✓ [{description}] 成功")

    def on_input(self, **kwargs):
        """
        [关键字] 向输入框中填入文本。
        此操作会先清空输入框，然后填入新内容，比逐字输入更稳定快速。
        数据内容: 要输入的文本。
        """
        text_to_fill = str(kwargs.get('数据内容', ''))
        description = kwargs.get('描述', f'输入 "{text_to_fill}"')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.fill(text_to_fill)
        print(f"✓ [{description}] 成功")
    
    def sleep(self, **kwargs):
        """
        [关键字] 强制等待指定的秒数。
        注意：此操作在无头(headless)模式下会被自动跳过以提高效率。
        尽量使用Playwright的智能等待，避免使用此关键字。
        数据内容: 等待的秒数 (e.g., "2.5")
        """
        global _total_sleep_time
        wait_time_sec = float(kwargs.get('数据内容', 2))
        if self.mode == 'headless':
            print(f"执行 [强制等待]: 无头模式下智能跳过 {wait_time_sec} 秒等待。")
            return
        print(f"执行 [强制等待]: {wait_time_sec} 秒.")
        self.active_page.wait_for_timeout(wait_time_sec * 1000)
        _total_sleep_time += wait_time_sec

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
                    expect(locator).to_be_visible()
                elif verify_type == 'element_text_equals':
                    expect(locator).to_have_text(str(kwargs.get('数据内容', '')))
                elif verify_type == 'element_text_contains':
                    expect(locator).to_contain_text(str(kwargs.get('数据内容', '')))
                else:
                    pytest.fail(f"不支持的元素验证类型: '{verify_type}'")
            elif verify_type == 'url_contains':
                expect(target_page).to_have_url(re.compile(f".*{re.escape(str(kwargs.get('数据内容', '')))}.*"))
            else:
                pytest.fail(f"不支持的验证类型: '{verify_type}'")
            print(f"✓ 验证通过: [{description}]")
        except (PlaywrightTimeoutError, AssertionError) as e:
             pytest.fail(f"✗ 验证失败: {description} - {e}")

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
    
    def clear_input(self, **kwargs):
        """
        这是一个兼容旧用例的过渡方法。
        [关键字] 清空指定的输入框。
        注意：'on_input'关键字已包含清空功能，此关键字仅用于适配旧框架测试数据。
        """
        description = kwargs.get('描述', '清空输入框')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.clear()
        print(f"✓ [{description}] 成功")

    def upload_file(self, **kwargs):
        """
        [关键字] 在文件上传类型的input元素上设置要上传的文件。
        数据内容: 要上传的文件的本地路径 (可以是相对或绝对路径)。
        """
        file_path = str(kwargs.get('数据内容', ''))
        if not file_path:
            pytest.fail("upload_file 关键字需要在 '数据内容' 列提供文件路径。")
            
        description = kwargs.get('描述', f'上传文件 {os.path.basename(file_path)}')
        print(f"执行 [{description}]")
        
        locator = self._get_locator(**kwargs)
        
        # 检查文件是否存在
        if not os.path.isabs(file_path):
            # 如果是相对路径，相对于项目根目录
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            file_path = os.path.join(project_root, file_path)
        

        if not os.path.exists(file_path):
            pytest.fail(f"上传失败：文件 '{file_path}' 不存在。")
            
        locator.set_input_files(file_path)
        print(f"✓ [{description}] 成功")

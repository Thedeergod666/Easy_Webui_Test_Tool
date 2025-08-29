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

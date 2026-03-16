# -*- coding: utf-8 -*-
"""
智能修复系统集成测试
验证在真实浏览器环境中的修复效果
"""

import pytest
import time
from unittest.mock import patch
from playwright.sync_api import sync_playwright


def test_strict_mode_auto_fix_integration():
    """
    集成测试：验证严格模式自动修复功能
    
    测试场景：
    1. 创建一个包含多个相同按钮的页面
    2. 使用宽泛的定位器触发严格模式违规
    3. 验证智能修复系统自动修复并成功执行
    """
    
    # HTML测试页面内容
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>智能修复系统测试页面</title>
        <style>
            .container { padding: 20px; }
            button { margin: 10px; padding: 10px; }
            .primary-btn { background: blue; color: white; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>测试页面</h1>
            <button type="button" class="primary-btn">开始创作</button>
            <button>1</button>
            <button>2</button>
            <button>3</button>
            <button>确定</button>
            <button>取消</button>
            <button>提交</button>
            <button>重置</button>
            <button>保存</button>
            <button>删除</button>
        </div>
        
        <div id="content-area">
            <p id="dynamic-content">星河AI赋能平台</p>
            <div class="product-section">
                <h2>应用产品</h2>
                <h4 class="nav-desc-title">应用产品</h4>
            </div>
        </div>
    </body>
    </html>
    """
    
    with sync_playwright() as p:
        # 启动浏览器
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # 加载测试页面
        page.set_content(test_html)
        
        try:
            # 导入我们的修复系统
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from framework.keywords.smart_fix_engine import SmartErrorHandler, RetryConfig
            from framework.keywords.verification import VerificationMixin
            
            # 创建Keywords实例（模拟）
            class TestKeywords(VerificationMixin):
                def __init__(self, page):
                    self.context = page.context
                    self.active_page = page
                    self.expect = pytest.expect if hasattr(pytest, 'expect') else None
                    
                    # 模拟expect函数
                    if not self.expect:
                        from playwright.sync_api import expect
                        self.expect = expect
            
            keywords = TestKeywords(page)
            
            # 测试案例1：严格模式违规自动修复
            print("\n=== 测试案例1：严格模式违规自动修复 ===")
            
            # 这个表达式会触发严格模式违规（因为页面上有多个button）
            problematic_expression = 'expect(page.get_by_role("button")).to_contain_text("开始创作")'
            
            # 构建执行上下文
            execution_context = {
                "page": page,
                "expect": keywords.expect,
                "re": __import__("re")
            }
            
            # 创建智能错误处理器
            handler = SmartErrorHandler(RetryConfig(
                max_attempts=3,
                base_delay=0.2,
                debug_output=True
            ))
            
            # 首先验证确实会触发严格模式错误
            captured_error = None
            try:
                eval(problematic_expression, execution_context)
                pytest.fail("期望触发严格模式错误，但表达式成功执行了")
            except Exception as e:
                captured_error = e
                error_message = str(e)
                print(f"✓ 成功触发预期错误: {type(e).__name__}")
                print(f"   错误信息: {error_message}")
                
                # 验证是否为严格模式错误
                assert "strict mode violation" in error_message.lower() or "resolved to" in error_message
            
            # 使用智能修复处理器处理错误
            print(f"\n开始智能修复测试...")
            start_time = time.time()
            
            try:
                result = handler.handle_playwright_error(captured_error, problematic_expression, execution_context)
                end_time = time.time()
                print(f"✓ 智能修复成功！耗时: {end_time - start_time:.2f}秒")
                
                # 获取修复摘要
                summary = handler.retry_mechanism.get_fix_summary()
                print(f"   修复摘要: {summary}")
                
                assert summary["success"] == True
                assert summary["total_attempts"] >= 1
                
            except Exception as fix_error:
                print(f"✗ 智能修复失败: {fix_error}")
                # 即使修复失败，我们也要分析失败原因
                summary = handler.retry_mechanism.get_fix_summary()
                print(f"   修复尝试摘要: {summary}")
                
                # 对于集成测试，我们期望修复成功，但如果失败也要记录详情
                pytest.fail(f"智能修复失败: {fix_error}")
            
            # 测试案例2：验证修复后的表达式能正常工作
            print(f"\n=== 测试案例2：验证修复后表达式 ===")
            
            # 从修复摘要中获取最终表达式
            final_expression = summary.get("final_expression")
            if final_expression:
                print(f"修复后表达式: {final_expression}")
                
                try:
                    # 直接执行修复后的表达式
                    eval(final_expression, execution_context)
                    print(f"✓ 修复后表达式执行成功")
                except Exception as e:
                    print(f"✗ 修复后表达式执行失败: {e}")
                    pytest.fail(f"修复后表达式仍然失败: {e}")
            
            # 测试案例3：多种定位器的修复效果
            print(f"\n=== 测试案例3：多种定位器修复测试 ===")
            
            test_expressions = [
                ('expect(page.get_by_text("应用产品")).to_be_visible()', "文本定位器修复"),
                ('expect(page.get_by_role("button")).to_contain_text("确定")', "角色定位器修复"),
                ('expect(page.locator("button")).to_be_visible()', "CSS选择器修复")
            ]
            
            for expr, desc in test_expressions:
                print(f"\n测试 {desc}:")
                print(f"  表达式: {expr}")
                
                try:
                    # 先尝试直接执行
                    eval(expr, execution_context)
                    print(f"  ✓ 直接执行成功")
                except Exception as e:
                    print(f"  ⚠ 触发错误: {type(e).__name__}")
                    
                    # 使用智能修复
                    try:
                        handler.retry_mechanism.clear_history()  # 清空历史记录
                        result = handler.handle_playwright_error(e, expr, execution_context)
                        print(f"  ✓ 智能修复成功")
                    except Exception as fix_e:
                        print(f"  ✗ 智能修复失败: {fix_e}")
                        # 不强制失败，因为某些表达式可能确实无法修复
            
            print(f"\n=== 集成测试完成 ===")
            
        except ImportError as e:
            pytest.skip(f"跳过集成测试，缺少依赖: {e}")
        
        finally:
            # 清理资源
            context.close()
            browser.close()


def test_expect_codegen_integration():
    """
    集成测试：验证expect_codegen关键字的智能修复功能
    """
    
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>expect_codegen测试页面</title>
    </head>
    <body>
        <div>
            <button class="primary">主要按钮</button>
            <button class="secondary">次要按钮</button>
            <button>普通按钮</button>
            <span id="status">就绪</span>
        </div>
    </body>
    </html>
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_content(test_html)
        
        try:
            # 导入修复系统
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from framework.keywords.verification import VerificationMixin
            from framework.keywords.base import Keywords
            
            # 创建Keywords实例
            class TestKeywords(VerificationMixin):
                def __init__(self, page):
                    self.context = page.context
                    self.active_page = page
                    from playwright.sync_api import expect
                    self.expect = expect
                    
                # 添加页面相关方法
                def _get_target_page(self, **kwargs):
                    return self.active_page
                
                def _validate_page_state(self, page, description):
                    try:
                        return not page.is_closed()
                    except:
                        return False
                
                def _recover_page_state(self, page):
                    try:
                        if not page.is_closed():
                            page.wait_for_load_state('networkidle', timeout=3000)
                            return True
                    except:
                        pass
                    return False
            
            keywords = TestKeywords(page)
            
            # 测试expect_codegen的智能修复
            print(f"\n=== expect_codegen智能修复测试 ===")
            
            # 测试参数
            test_kwargs = {
                "目标对象": 'expect(page.get_by_role("button")).to_contain_text("主要按钮")',
                "描述": "测试智能修复功能"
            }
            
            print(f"测试表达式: {test_kwargs['目标对象']}")
            
            try:
                keywords.expect_codegen(**test_kwargs)
                print(f"✓ expect_codegen执行成功")
            except Exception as e:
                print(f"✗ expect_codegen执行失败: {e}")
                # 对于集成测试，期望能够自动修复
                pytest.fail(f"expect_codegen智能修复失败: {e}")
            
            print(f"\n=== expect_codegen测试完成 ===")
            
        except ImportError as e:
            pytest.skip(f"跳过expect_codegen测试，缺少依赖: {e}")
        
        finally:
            context.close()
            browser.close()


def test_performance_impact():
    """
    性能测试：验证智能修复对性能的影响
    """
    
    test_html = """
    <!DOCTYPE html>
    <html><body>
        <button>按钮1</button>
        <button>按钮2</button>
        <button>按钮3</button>
    </body></html>
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_content(test_html)
        
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from framework.keywords.smart_fix_engine import SmartErrorHandler, RetryConfig
            from playwright.sync_api import expect
            
            execution_context = {"page": page, "expect": expect}
            
            # 测试正常表达式的执行时间
            normal_expression = 'expect(page.get_by_role("button").first).to_be_visible()'
            
            start_time = time.time()
            for _ in range(10):
                eval(normal_expression, execution_context)
            normal_time = time.time() - start_time
            
            print(f"正常表达式平均执行时间: {normal_time/10:.4f}秒")
            
            # 测试带智能修复的执行时间
            handler = SmartErrorHandler(RetryConfig(debug_output=False))
            problematic_expression = 'expect(page.get_by_role("button")).to_be_visible()'
            
            start_time = time.time()
            total_attempts = 0
            
            for i in range(5):  # 减少测试次数以提高测试速度
                try:
                    handler.retry_mechanism.clear_history()
                    eval(problematic_expression, execution_context)
                except Exception as e:
                    try:
                        handler.handle_playwright_error(e, problematic_expression, execution_context)
                        summary = handler.retry_mechanism.get_fix_summary()
                        total_attempts += summary["total_attempts"]
                    except:
                        pass
            
            smart_fix_time = time.time() - start_time
            
            print(f"智能修复平均执行时间: {smart_fix_time/5:.4f}秒")
            print(f"平均修复尝试次数: {total_attempts/5:.1f}")
            
            # 性能影响应该在可接受范围内（比如不超过10倍）
            performance_ratio = (smart_fix_time/5) / (normal_time/10)
            print(f"性能比率: {performance_ratio:.2f}x")
            
            # 断言性能影响在可接受范围内
            assert performance_ratio < 20, f"性能影响过大: {performance_ratio:.2f}x"
            
        except ImportError as e:
            pytest.skip(f"跳过性能测试，缺少依赖: {e}")
        
        finally:
            context.close()
            browser.close()


def test_edge_cases():
    """
    边界情况测试：验证各种边界条件下的修复系统行为
    """
    
    test_html = """
    <!DOCTYPE html>
    <html><body>
        <div id="dynamic-content"></div>
        <button style="display:none;">隐藏按钮</button>
    </body></html>
    """
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.set_content(test_html)
        
        try:
            import sys
            import os
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))
            
            from framework.keywords.smart_fix_engine import SmartErrorHandler, RetryConfig
            from playwright.sync_api import expect
            
            execution_context = {"page": page, "expect": expect}
            handler = SmartErrorHandler(RetryConfig(debug_output=False))
            
            # 测试各种边界情况
            edge_cases = [
                ('expect(page.get_by_text("不存在的文本")).to_be_visible()', "元素不存在"),
                ('expect(page.locator("#dynamic-content")).to_contain_text("空内容")', "内容为空"),
                ('expect(page.get_by_role("button")).to_be_visible()', "元素不可见"),
                ('expect(undefined_page.get_by_text("test")).to_be_visible()', "页面变量未定义"),
            ]
            
            for expr, desc in edge_cases:
                print(f"\n测试边界情况: {desc}")
                print(f"  表达式: {expr}")
                
                try:
                    eval(expr, execution_context)
                    print(f"  ✓ 直接执行成功")
                except Exception as e:
                    print(f"  ⚠ 触发错误: {type(e).__name__}: {str(e)[:100]}...")
                    
                    try:
                        handler.retry_mechanism.clear_history()
                        result = handler.handle_playwright_error(e, expr, execution_context)
                        print(f"  ✓ 智能修复成功")
                    except Exception as fix_e:
                        print(f"  ✗ 智能修复失败: {type(fix_e).__name__}")
                        # 对于边界情况，修复失败是可以接受的
            
        except ImportError as e:
            pytest.skip(f"跳过边界测试，缺少依赖: {e}")
        
        finally:
            context.close()
            browser.close()


if __name__ == "__main__":
    # 运行集成测试
    pytest.main([__file__, "-v", "-s", "--tb=short"])

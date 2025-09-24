# tests/conftest.py (V3 - 终极简化版)
import pytest
import sys
import os
import json
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入Keywords是为了在最后报告时拿到那个全局变量
from framework import Keywords as KeywordsModule
from framework.Keywords import Keywords
# 导入ReportLogger用于测试步骤记录
from framework.utils.report_logger import ReportLogger

def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--flow-config-file",
        action="store",
        help="指定测试流程配置文件路径"
    )
    parser.addoption(
        "--screenshots-dir",
        action="store",
        default=".",
        help="指定截图保存目录路径"
    )

# --- Fixture 1: 加载JSON配置，只执行一次 ---
@pytest.fixture(scope="session")
def framework_config():
    config_path = os.path.join(project_root, 'test_data', 'test_config.json')
    if not os.path.exists(config_path):
        pytest.fail(f"全局配置文件 test_config.json 不存在于 '{config_path}'!")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

# --- Fixture: 截图目录配置 ---
@pytest.fixture(scope="function")
def screenshots_dir(request):
    """获取截图目录路径"""
    return request.config.getoption("--screenshots-dir")

@pytest.fixture(scope="session")
def screenshots_dir_session(request):
    """获取session级别的截图目录路径"""
    return request.config.getoption("--screenshots-dir")

# --- Fixture 2: 决定浏览器启动参数 (有头/无头/慢动作) ---
@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args, framework_config, request):
    """
    智能地决定浏览器启动参数，并把最终的运行模式存入 request.config 中。
    """
    cmd_has_headed = "--headed" in sys.argv
    visual_config = framework_config.get("visual_mode", {})
    json_headed = visual_config.get("headed", False)
    
    final_mode = "headed" # 默认为有头
    
    if cmd_has_headed:
        print("\n[配置] 检测到命令行 --headed，将以有头模式运行。")
        final_mode = "headed"
    else:
        print(f"\n[配置] 未检测到命令行 --headed，使用JSON配置 (headed={json_headed})。")
        final_mode = "headed" if json_headed else "headless"

    # 将最终的运行模式存放到 pytest 的全局 config 对象中，以便后续 fixture 使用
    request.config.cache.set("running_mode", final_mode)

    return {
        **browser_type_launch_args,
        "headless": final_mode == "headless",
        "slow_mo": visual_config.get("slow_mo", 0)
    }

# --- Fixture 3: 创建 Keywords 实例，并注入运行模式 ---
def set_running_mode_on_page(page, request, report_logger_name="report_logger"):
    """一个辅助函数，用于将运行模式附加到 page 对象上"""
    running_mode = request.config.cache.get("running_mode", "headed")
    # 我们将模式信息附加到 context 上，这是一个稳定的宿主
    page.context.running_mode = running_mode
    # 获取report_logger实例
    report_logger = request.getfixturevalue(report_logger_name)
    return Keywords(page, report_logger)

@pytest.fixture(scope="function")
def report_logger(page):
    """创建ReportLogger实例，用于记录测试步骤"""
    return ReportLogger(page)

@pytest.fixture(scope="session")
def report_logger_session(page_session):
    """创建session级别的ReportLogger实例，用于记录测试步骤"""
    return ReportLogger(page_session)

@pytest.fixture(scope="function")
def keywords_func(page, request):
    return set_running_mode_on_page(page, request)

@pytest.fixture(scope="session")
def page_session(browser):
    """创建 session 级别的 page 对象"""
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()
    
@pytest.fixture(scope="session")
def keywords_session(page_session, request):
    return set_running_mode_on_page(page_session, request, "report_logger_session")


# --- Hook 4: 在测试结束后，报告 sleep 总时间 ---
def pytest_sessionfinish(session, exitstatus):
    """
    在整个测试会话结束时被调用。
    """
    # 直接从 Keywords 模块拿到那个全局变量
    total_sleep = KeywordsModule._total_sleep_time
    if total_sleep > 0:
        # 使用 pytest 的方式来打印报告
        reporter = session.config.pluginmanager.getplugin('terminalreporter')
        reporter.write_sep("=", "强制等待 (sleep) 耗时统计", yellow=True)
        reporter.write_line(f"在有头模式下, 所有测试中 'sleep' 关键字的总耗时为: {total_sleep:.2f} 秒")


# --- Hook 5: 在测试用例执行后，生成详细的HTML报告 ---
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    在测试用例执行后生成详细的HTML报告。
    这个钩子会在每个测试阶段（setup, call, teardown）都会被调用，
    我们只在call阶段完成后处理报告生成。
    """
    # 先执行默认的报告生成逻辑
    outcome = yield
    report = outcome.get_result()
    
    # 只在call阶段完成后处理报告生成
    if report.when == "call":
        try:
            # 处理失败截图的HTML集成
            if report.failed and hasattr(item, "funcargs"):
                # 获取截图路径
                screenshot_path = None
                
                # Session模式下的截图处理
                if "keywords_session" in item.funcargs and "screenshots_dir_session" in item.funcargs:
                    keywords_session = item.funcargs["keywords_session"]
                    screenshots_dir_session = item.funcargs["screenshots_dir_session"]
                    test_step = item.funcargs.get("test_step", {})
                    step_id = test_step.get('编号', 'unknown_step')
                    
                    # 先尝试生成失败截图
                    try:
                        if hasattr(keywords_session, 'active_page') and keywords_session.active_page:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
                            screenshot_filename = f"error_{step_id}_{timestamp}.png"
                            screenshot_path = os.path.join(screenshots_dir_session, screenshot_filename)
                            
                            # 确保目录存在
                            os.makedirs(screenshots_dir_session, exist_ok=True)
                            
                            # 生成截图
                            keywords_session.active_page.screenshot(path=screenshot_path, full_page=True)
                            print(f"📷  Session模式失败截图已生成: {screenshot_path}")
                    except Exception as e:
                        print(f"📷  Session模式生成失败截图失败: {e}")
                        # 如果生成失败，尝试查找已存在的截图文件
                        import glob
                        error_screenshots = glob.glob(os.path.join(screenshots_dir_session, f"error_{step_id}_*.png"))
                        if error_screenshots:
                            error_screenshots.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                            screenshot_path = error_screenshots[0]
                            print(f"📷  Session模式找到已存在的错误截图: {screenshot_path}")
                
                # Function模式下的截图处理
                elif "screenshots_dir" in item.funcargs:
                    screenshots_dir = item.funcargs["screenshots_dir"]
                    # 查找最新的错误截图文件
                    import glob
                    error_screenshots = glob.glob(os.path.join(screenshots_dir, "error_*.png"))
                    if error_screenshots:
                        # 按修改时间排序，获取最新的截图
                        error_screenshots.sort(key=lambda x: os.path.getmtime(x), reverse=True)
                        screenshot_path = error_screenshots[0]
                        print(f"📷  Function模式找到错误截图: {screenshot_path}")
                
                # 将截图添加到pytest-html报告
                if screenshot_path and os.path.exists(screenshot_path):
                    print(f"📷  开始集成截图到HTML报告，截图路径: {screenshot_path}")
                    
                    # 使用pytest_html的正确API添加截图
                    try:
                        import pytest_html
                        
                        # 方法1：使用pytest_html.extras.image()直接添加截图文件
                        extras = getattr(report, "extras", [])
                        
                        # 读取截图文件并转换为base64
                        import base64
                        with open(screenshot_path, "rb") as image_file:
                            image_data = base64.b64encode(image_file.read()).decode()
                        
                        # 使用pytest_html.extras.png()添加截图
                        extras.append(pytest_html.extras.png(image_data, name="失败截图"))
                        
                        # 添加额外的HTML信息
                        screenshot_name = os.path.basename(screenshot_path)
                        relative_path = f"screenshots/{screenshot_name}"
                        
                        extra_html = f'''
                        <div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f8f9fa;">
                            <h4 style="color: #d9534f; margin-top: 0;">📷 失败截图信息</h4>
                            <p><strong>截图文件:</strong> <code>{relative_path}</code></p>
                            <p><strong>截图时间:</strong> {datetime.fromtimestamp(os.path.getmtime(screenshot_path)).strftime('%Y-%m-%d %H:%M:%S')}</p>
                        </div>
                        '''
                        
                        extras.append(pytest_html.extras.html(extra_html))
                        
                        # 确保extras被正确设置到report
                        report.extras = extras
                        print(f"📷  ✅ 截图已成功集成到HTML报告，extras数量: {len(extras)}")
                        
                    except ImportError:
                        print(f"📷  ❌ 未安装pytest-html插件，无法集成截图")
                    except Exception as e:
                        print(f"📷  ❌ 集成截图时出错: {e}")
                else:
                    print(f"📷  截图路径为空或文件不存在: {screenshot_path}")
            
            # 从item中获取report_logger实例
            # 如果fixture没有被使用，则会抛出异常，我们直接忽略
            report_logger = item.funcargs.get("report_logger")
            
            # 只有当report_logger存在且有步骤记录时才生成报告
            if report_logger and report_logger.steps:
                # 生成HTML内容
                html_content = report_logger.to_html()
                
                # 将HTML内容添加到报告中
                if hasattr(report, "extra"):
                    report.extra.append(html_content)
                else:
                    report.extra = [html_content]
        except Exception as e:
            # 添加错误处理，避免因为报告生成问题影响测试执行
            print(f"生成详细报告时出错: {e}")

# tests/conftest.py (V3 - 终极简化版)
import pytest
import sys
import os
import json
import base64
import glob
from datetime import datetime

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入Keywords是为了在最后报告时拿到那个全局变量
from framework import Keywords as KeywordsModule
from framework.Keywords import Keywords
# 导入ReportLogger用于测试步骤记录
from framework.utils.report_logger import ReportLogger
from framework.utils.reporting_support import append_pytest_html_extra, get_report_logger

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


def _append_html_report_extra(report, extra):
    """统一向 pytest-html 报告追加附件。"""
    return append_pytest_html_extra(report, extra)


def _get_keywords_fixture(funcargs):
    return funcargs.get("keywords_func") or funcargs.get("keywords_session")


def _get_screenshots_dir(funcargs):
    return funcargs.get("screenshots_dir") or funcargs.get("screenshots_dir_session")


def _build_try_screenshot_html(step_id, timestamp, path):
    return f"""
    <div style="margin: 10px 0; padding: 10px; border-left: 4px solid #ff9800; background-color: #fff3cd;">
        <h4 style="color: #856404; margin-top: 0;">Try状态失败截图</h4>
        <p><strong>步骤ID:</strong> {step_id}</p>
        <p><strong>失败时间:</strong> {timestamp}</p>
        <p><strong>截图文件:</strong> <code>{os.path.basename(path)}</code></p>
        <p><strong>状态:</strong> <span style="color: #ff9800;">尝试失败但已跳过</span></p>
    </div>
    """


def _build_failure_screenshot_html(screenshot_path):
    screenshot_name = os.path.basename(screenshot_path)
    relative_path = f"screenshots/{screenshot_name}"
    screenshot_time = datetime.fromtimestamp(os.path.getmtime(screenshot_path)).strftime('%Y-%m-%d %H:%M:%S')
    return f"""
    <div style="margin: 10px 0; padding: 10px; border: 1px solid #ddd; border-radius: 4px; background-color: #f8f9fa;">
        <h4 style="color: #d9534f; margin-top: 0;">失败截图信息</h4>
        <p><strong>截图文件:</strong> <code>{relative_path}</code></p>
        <p><strong>截图时间:</strong> {screenshot_time}</p>
    </div>
    """


def _append_png_extra(report, image_path, name):
    import pytest_html

    with open(image_path, "rb") as image_file:
        image_data = base64.b64encode(image_file.read()).decode()

    _append_html_report_extra(report, pytest_html.extras.png(image_data, name=name))


def _append_html_extra(report, html_content):
    import pytest_html

    _append_html_report_extra(report, pytest_html.extras.html(html_content))


def _consume_try_failure_screenshots(keywords):
    screenshots = list(getattr(keywords, "_try_failure_screenshots", []))
    if hasattr(keywords, "_try_failure_screenshots"):
        keywords._try_failure_screenshots = []
    return screenshots


def _attach_try_failure_screenshots(report, keywords):
    for try_screenshot in _consume_try_failure_screenshots(keywords):
        try_path = try_screenshot["path"]
        if not os.path.exists(try_path):
            continue

        step_id = try_screenshot["step_id"]
        timestamp = try_screenshot["timestamp"]
        print(f"[REPORT] 处理Try失败截图: {try_path}")
        _append_png_extra(report, try_path, f"Try失败截图 - 步骤 {step_id}")
        _append_html_extra(report, _build_try_screenshot_html(step_id, timestamp, try_path))


def _resolve_failure_screenshot_path(funcargs):
    keywords = _get_keywords_fixture(funcargs)
    screenshots_dir = _get_screenshots_dir(funcargs)
    if not keywords or not screenshots_dir:
        return None

    test_step = funcargs.get("test_step", {})
    step_id = test_step.get("编号", "unknown_step")

    try:
        if hasattr(keywords, "active_page") and keywords.active_page:
            os.makedirs(screenshots_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
            screenshot_path = os.path.join(screenshots_dir, f"error_{step_id}_{timestamp}.png")
            keywords.active_page.screenshot(path=screenshot_path, full_page=True)
            print(f"[REPORT] 失败截图已生成: {screenshot_path}")
            return screenshot_path
    except Exception as error:
        print(f"[REPORT] 生成失败截图失败: {error}")

    error_screenshots = glob.glob(os.path.join(screenshots_dir, f"error_{step_id}_*.png"))
    if not error_screenshots:
        error_screenshots = glob.glob(os.path.join(screenshots_dir, "error_*.png"))
    if not error_screenshots:
        return None

    error_screenshots.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    return error_screenshots[0]


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
    if report.when != "call":
        return

    try:
        funcargs = getattr(item, "funcargs", {})
        keywords = _get_keywords_fixture(funcargs)
        if keywords:
            _attach_try_failure_screenshots(report, keywords)

        if report.failed:
            screenshot_path = _resolve_failure_screenshot_path(funcargs)
            if screenshot_path and os.path.exists(screenshot_path):
                print(f"[REPORT] 开始集成失败截图: {screenshot_path}")
                _append_png_extra(report, screenshot_path, "失败截图")
                _append_html_extra(report, _build_failure_screenshot_html(screenshot_path))
            else:
                print(f"[REPORT] 截图路径为空或文件不存在: {screenshot_path}")

        report_logger = get_report_logger(funcargs)
        if report_logger and report_logger.steps:
            _append_html_extra(report, report_logger.to_html())
    except ImportError:
        print("[REPORT] 未安装pytest-html插件，跳过HTML附件集成")
    except Exception as error:
        print(f"生成详细报告时出错: {error}")

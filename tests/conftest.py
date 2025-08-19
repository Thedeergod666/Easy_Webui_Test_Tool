# tests/conftest.py (V3 - 终极简化版)
import pytest
import sys
import os
import json

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入Keywords是为了在最后报告时拿到那个全局变量
from framework import Keywords as KeywordsModule
from framework.Keywords import Keywords

def pytest_addoption(parser):
    """添加自定义命令行选项"""
    parser.addoption(
        "--flow-config-file",
        action="store",
        help="指定测试流程配置文件路径"
    )

# --- Fixture 1: 加载JSON配置，只执行一次 ---
@pytest.fixture(scope="session")
def framework_config():
    config_path = os.path.join(project_root, 'test_data', 'test_config.json')
    if not os.path.exists(config_path):
        pytest.fail(f"全局配置文件 test_config.json 不存在于 '{config_path}'!")
    with open(config_path, 'r', encoding='utf-8') as f:
        return json.load(f)

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
def set_running_mode_on_page(page, request):
    """一个辅助函数，用于将运行模式附加到 page 对象上"""
    running_mode = request.config.cache.get("running_mode", "headed")
    # 我们将模式信息附加到 context 上，这是一个稳定的宿主
    page.context.running_mode = running_mode
    return Keywords(page)

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
    return set_running_mode_on_page(page_session, request)


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

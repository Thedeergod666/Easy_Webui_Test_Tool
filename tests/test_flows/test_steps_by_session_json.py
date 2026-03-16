# -*- coding: utf-8 -*-
"""基于 JSON 配置的 session 测试流。"""

import json
import os
import sys

import pandas as pd
import pytest

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
framework_root = os.path.join(project_root, "framework")
if framework_root not in sys.path:
    sys.path.append(framework_root)

from tests.helpers.step_flow_runner import execute_test_step


def load_test_data_from_config(config_file=None):
    """从配置文件加载启用的测试流程。"""
    if config_file and os.path.exists(config_file):
        config_path = config_file
        with open(config_path, "r", encoding="utf-8") as file:
            flows = json.load(file)
        return [flow for flow in flows if isinstance(flow, dict)]

    config_path = os.path.join(project_root, "test_data", "test_config.json")
    if not os.path.exists(config_path):
        print(f"[WARN] 测试配置文件不存在: {config_path}")
        return []

    with open(config_path, "r", encoding="utf-8") as file:
        config = json.load(file)

    flows = config.get("test_flows", [])
    enabled_flows = [flow for flow in flows if isinstance(flow, dict) and flow.get("enabled", True)]
    for flow in enabled_flows:
        flow.setdefault("browser", "chromium")
    return enabled_flows


def _resolve_excel_path(excel_file):
    if os.path.isabs(excel_file):
        return excel_file
    return os.path.join(project_root, excel_file)


def _load_steps_from_flows(flow_configs):
    all_steps = []
    for flow_config in flow_configs:
        excel_path = _resolve_excel_path(flow_config["file_path"])
        sheet_name = flow_config["sheet_name"]
        print(f"[DEBUG] 尝试加载流程: {excel_path} (Sheet: {sheet_name})")
        if not os.path.exists(excel_path):
            print(f"[WARN] 测试文件不存在: {excel_path}")
            continue

        steps = pd.read_excel(excel_path, sheet_name=sheet_name).fillna("").to_dict(orient="records")
        print(f"[DEBUG] 从 {excel_path} 加载到 {len(steps)} 个测试步骤")
        all_steps.extend(steps)
    return all_steps


def pytest_generate_tests(metafunc):
    """动态生成测试参数。"""
    config_file = metafunc.config.getoption("--flow-config-file", None)
    flow_configs = load_test_data_from_config(config_file)

    if "flow_config" in metafunc.fixturenames:
        metafunc.parametrize("flow_config", flow_configs, scope="session")
        return

    if "test_step" in metafunc.fixturenames:
        metafunc.parametrize("test_step", _load_steps_from_flows(flow_configs))


def test_single_step(keywords_session, test_step, screenshots_dir_session):
    execute_test_step(keywords_session, test_step, screenshots_dir_session)


if __name__ == "__main__":
    pytest.main(["-s", "-v", __file__])

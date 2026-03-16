# -*- coding: utf-8 -*-
"""CLI workflow regression tests for init/validate and non-interactive execution."""

import importlib
import json
from pathlib import Path

from openpyxl import Workbook

from framework.utils import executor as executor_module
from framework.utils import main as main_module
from framework.utils.run_tests import runner as runner_module


def _create_excel(path: Path, sheet_name: str = "Sheet1") -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    worksheet["A1"] = "编号"
    workbook.save(path)


def test_initialize_test_config_creates_default_config_with_existing_sample(tmp_path):
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()
    _create_excel(test_data_dir / "simple_test.xlsx")

    config_workflow = importlib.import_module("framework.utils.config_workflow")

    result = config_workflow.initialize_test_config(tmp_path)
    config = json.loads((test_data_dir / "test_config.json").read_text(encoding="utf-8"))

    assert result.exit_code == 0
    assert config["test_flows"][0]["file_path"] == "test_data/simple_test.xlsx"
    assert config["test_flows"][0]["enabled"] is True


def test_validate_test_config_reports_invalid_browser_and_missing_file(tmp_path):
    test_data_dir = tmp_path / "test_data"
    test_data_dir.mkdir()
    (test_data_dir / "test_config.json").write_text(
        json.dumps(
            {
                "visual_mode": {"headed": True, "slow_mo": 50},
                "test_flows": [
                    {
                        "file_path": "test_data/missing.xlsx",
                        "sheet_name": "Sheet1",
                        "description": "missing file",
                        "browser": "safari",
                        "enabled": True,
                    }
                ],
            },
            ensure_ascii=False,
            indent=4,
        ),
        encoding="utf-8",
    )

    config_workflow = importlib.import_module("framework.utils.config_workflow")

    result = config_workflow.validate_test_config(tmp_path)

    assert result.is_valid is False
    assert any("safari" in error for error in result.errors)
    assert any("missing.xlsx" in error for error in result.errors)


def test_execute_function_uses_non_interactive_case_listing(monkeypatch):
    recorded = {}

    def fake_view_test_cases(*, non_interactive=False):
        recorded["non_interactive"] = non_interactive
        return 0

    monkeypatch.setattr(executor_module, "view_test_cases", fake_view_test_cases)

    assert executor_module.FunctionExecutor.execute_function("9", ci_mode=True) == 0
    assert recorded["non_interactive"] is True


def test_main_returns_execute_function_status(monkeypatch):
    monkeypatch.setattr(main_module, "ensure_test_config_exists", lambda: None)
    monkeypatch.setattr(
        main_module.FunctionExecutor,
        "parse_command_args",
        staticmethod(lambda args: ("validate", None)),
    )
    monkeypatch.setattr(
        main_module.FunctionExecutor,
        "execute_function",
        staticmethod(lambda func_id, args, ci_mode: 7),
    )

    assert main_module.main(["validate"]) == 7


def test_run_tests_returns_failure_when_any_batch_fails(monkeypatch):
    flows = [
        {
            "file_path": "test_data/flow_a.xlsx",
            "sheet_name": "Sheet1",
            "description": "flow a",
            "browser": "chromium",
            "enabled": True,
        },
        {
            "file_path": "test_data/flow_b.xlsx",
            "sheet_name": "Sheet1",
            "description": "flow b",
            "browser": "firefox",
            "enabled": True,
        },
    ]

    monkeypatch.setattr(runner_module, "get_test_flows", lambda: flows)
    monkeypatch.setattr(
        runner_module,
        "run_pytest_batch",
        lambda browser, flows_for_browser, test_file_path, ci_mode=False: browser == "chromium",
    )

    assert runner_module.run_tests("1", ci_mode=True) == 1

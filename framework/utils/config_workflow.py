# -*- coding: utf-8 -*-
"""Shared helpers for initializing and validating test_config.json."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_RELATIVE_PATH = Path("test_data") / "test_config.json"
SUPPORTED_BROWSERS = {
    "cr": "chromium",
    "ff": "firefox",
    "wk": "webkit",
    "chromium": "chromium",
    "firefox": "firefox",
    "webkit": "webkit",
}


@dataclass
class WorkflowResult:
    """Result payload for config init/validate commands."""

    exit_code: int
    config_path: Path
    messages: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    created: bool = False
    updated: bool = False
    data: dict[str, Any] | None = None

    @property
    def is_valid(self) -> bool:
        return not self.errors


def resolve_project_root(project_root: str | Path | None = None) -> Path:
    """Resolve the project root for config operations."""
    return Path(project_root) if project_root else PROJECT_ROOT


def get_config_path(project_root: str | Path | None = None) -> Path:
    """Return the absolute path to test_config.json."""
    return resolve_project_root(project_root) / CONFIG_RELATIVE_PATH


def _default_sample_relative_path(root: Path) -> str:
    candidate = root / "test_data" / "simple_test.xlsx"
    if candidate.exists():
        return "test_data/simple_test.xlsx"
    return "test_data/sample_test.xlsx"


def build_default_config(project_root: str | Path | None = None) -> dict[str, Any]:
    """Build a safe default config that points at the bundled example when available."""
    root = resolve_project_root(project_root)
    sample_relative_path = _default_sample_relative_path(root)
    sample_exists = (root / sample_relative_path).exists()
    description = "示例测试流程（可直接修改或替换）"
    if not sample_exists:
        description = "示例测试流程（请先准备 Excel 用例后再启用）"

    return {
        "visual_mode": {
            "headed": True,
            "slow_mo": 50,
            "report_type": "both",
        },
        "enable_excel_colorization": True,
        "test_flows": [
            {
                "file_path": sample_relative_path,
                "sheet_name": "Sheet1",
                "description": description,
                "browser": "chromium",
                "enabled": sample_exists,
            }
        ],
    }


def _load_config_from_path(config_path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not config_path.exists():
        return None, [f"配置文件不存在: {config_path}"]

    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        return None, [f"配置文件 JSON 格式错误: {config_path} ({error.msg})"]

    if not isinstance(data, dict):
        return None, [f"配置文件根节点必须是 JSON 对象: {config_path}"]

    return data, []


def load_test_config(project_root: str | Path | None = None) -> WorkflowResult:
    """Load test_config.json without performing full validation."""
    config_path = get_config_path(project_root)
    data, errors = _load_config_from_path(config_path)
    return WorkflowResult(
        exit_code=0 if not errors else 1,
        config_path=config_path,
        errors=errors,
        data=data,
    )


def validate_test_config(project_root: str | Path | None = None) -> WorkflowResult:
    """Validate test_config.json and referenced Excel files."""
    root = resolve_project_root(project_root)
    config_path = get_config_path(root)
    data, errors = _load_config_from_path(config_path)
    warnings: list[str] = []

    if errors:
        return WorkflowResult(exit_code=1, config_path=config_path, errors=errors)

    assert data is not None
    visual_mode = data.get("visual_mode", {})
    if visual_mode and not isinstance(visual_mode, dict):
        errors.append("visual_mode 必须是对象")

    test_flows = data.get("test_flows")
    if not isinstance(test_flows, list):
        errors.append("test_flows 必须是数组")
        return WorkflowResult(
            exit_code=1,
            config_path=config_path,
            errors=errors,
            warnings=warnings,
            data=data,
        )

    if not test_flows:
        warnings.append("test_flows 为空，当前没有可执行的流程")

    enabled_count = 0
    seen_flow_keys: set[tuple[str, str]] = set()
    for index, flow in enumerate(test_flows, start=1):
        flow_label = f"第 {index} 个流程"
        if not isinstance(flow, dict):
            errors.append(f"{flow_label} 不是对象")
            continue

        file_path = flow.get("file_path")
        sheet_name = flow.get("sheet_name")
        description = flow.get("description")
        browser = flow.get("browser", "chromium")
        enabled = flow.get("enabled", True)

        if enabled:
            enabled_count += 1

        if not file_path or not isinstance(file_path, str):
            errors.append(f"{flow_label} 缺少有效的 file_path")
            continue
        if not sheet_name or not isinstance(sheet_name, str):
            errors.append(f"{flow_label} 缺少有效的 sheet_name")
        if not description or not isinstance(description, str):
            errors.append(f"{flow_label} 缺少有效的 description")
        if not isinstance(browser, str) or browser.lower() not in SUPPORTED_BROWSERS:
            errors.append(f"{flow_label} 使用了不支持的 browser: {browser}")

        resolved_path = Path(file_path)
        if resolved_path.is_absolute():
            warnings.append(f"{flow_label} 使用了绝对路径，迁移仓库时可能失效: {file_path}")
        else:
            resolved_path = root / resolved_path

        normalized_key = (str(resolved_path).lower(), str(sheet_name))
        if normalized_key in seen_flow_keys:
            warnings.append(f"{flow_label} 与前面的流程重复引用了同一个文件和 Sheet: {file_path} / {sheet_name}")
        else:
            seen_flow_keys.add(normalized_key)

        if not resolved_path.exists():
            errors.append(f"{flow_label} 引用的 Excel 文件不存在: {resolved_path}")
            continue

        try:
            excel_file = pd.ExcelFile(resolved_path)
            if sheet_name not in excel_file.sheet_names:
                errors.append(
                    f"{flow_label} 引用的 Sheet 不存在: {sheet_name} (可用: {', '.join(excel_file.sheet_names)})"
                )
        except Exception as error:  # pragma: no cover - defensive
            errors.append(f"{flow_label} 无法读取 Excel 文件 {resolved_path}: {error}")

    if enabled_count == 0:
        warnings.append("所有流程当前都处于 disabled 状态")

    messages = [f"已校验配置文件: {config_path}"]
    if not errors:
        messages.append("配置校验通过")

    return WorkflowResult(
        exit_code=0 if not errors else 1,
        config_path=config_path,
        messages=messages,
        warnings=warnings,
        errors=errors,
        data=data,
    )


def initialize_test_config(project_root: str | Path | None = None) -> WorkflowResult:
    """Create or repair test_config.json using the bundled sample flow."""
    root = resolve_project_root(project_root)
    test_data_dir = root / "test_data"
    config_path = test_data_dir / "test_config.json"
    test_data_dir.mkdir(parents=True, exist_ok=True)

    created = False
    updated = False
    messages: list[str] = []

    existing = load_test_config(root)
    if existing.exit_code == 0:
        validation = validate_test_config(root)
        if validation.is_valid:
            validation.messages.insert(0, f"配置文件已存在且可用: {config_path}")
            return validation

        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.with_name(f"test_config.json.{backup_suffix}.backup")
        config_path.replace(backup_path)
        updated = True
        messages.append(f"检测到无效配置，已备份到: {backup_path}")
    elif config_path.exists():
        backup_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = config_path.with_name(f"test_config.json.{backup_suffix}.backup")
        config_path.replace(backup_path)
        updated = True
        messages.append(f"检测到损坏配置，已备份到: {backup_path}")
    else:
        created = True

    default_config = build_default_config(root)
    config_path.write_text(
        json.dumps(default_config, ensure_ascii=False, indent=4),
        encoding="utf-8",
    )
    action = "已创建默认配置文件" if created else "已重建默认配置文件"
    messages.append(f"{action}: {config_path}")

    validation = validate_test_config(root)
    return WorkflowResult(
        exit_code=validation.exit_code,
        config_path=config_path,
        messages=messages + validation.messages,
        warnings=validation.warnings,
        errors=validation.errors,
        created=created,
        updated=updated,
        data=validation.data,
    )


def print_workflow_result(result: WorkflowResult) -> None:
    """Render a workflow result for CLI output."""
    for message in result.messages:
        print(f"[信息] {message}")
    for warning in result.warnings:
        print(f"[警告] {warning}")
    for error in result.errors:
        print(f"[错误] {error}")

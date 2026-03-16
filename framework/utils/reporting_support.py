# -*- coding: utf-8 -*-
"""pytest 报告辅助函数。"""

from typing import Any, Mapping, Optional


def append_pytest_html_extra(report: Any, extra: Any) -> list[Any]:
    """统一将附件追加到 pytest-html 使用的 `report.extras`。"""
    extras = list(getattr(report, "extras", []) or [])
    extras.append(extra)
    report.extras = extras
    return extras


def get_report_logger(funcargs: Optional[Mapping[str, Any]]) -> Any:
    """优先返回 function 级 logger，缺失时回退到 session 级 logger。"""
    if not funcargs:
        return None
    return funcargs.get("report_logger") or funcargs.get("report_logger_session")

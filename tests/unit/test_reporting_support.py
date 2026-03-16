# -*- coding: utf-8 -*-
"""pytest HTML 报告辅助函数测试"""

from types import SimpleNamespace

from framework.utils.reporting_support import (
    append_pytest_html_extra,
    get_report_logger,
)


def test_append_pytest_html_extra_initializes_extras_list():
    report = SimpleNamespace()

    append_pytest_html_extra(report, "html-extra")

    assert report.extras == ["html-extra"]
    assert not hasattr(report, "extra")


def test_append_pytest_html_extra_preserves_existing_extras():
    report = SimpleNamespace(extras=["png-extra"])

    append_pytest_html_extra(report, "html-extra")

    assert report.extras == ["png-extra", "html-extra"]


def test_get_report_logger_supports_session_fixture_fallback():
    session_logger = object()

    assert get_report_logger({"report_logger_session": session_logger}) is session_logger


def test_get_report_logger_prefers_function_logger_when_available():
    function_logger = object()
    session_logger = object()

    assert get_report_logger(
        {
            "report_logger": function_logger,
            "report_logger_session": session_logger,
        }
    ) is function_logger

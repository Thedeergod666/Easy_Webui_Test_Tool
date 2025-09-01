# -*- coding: utf-8 -*-
"""
基础模块
提供关键字框架的基础类和通用功能
"""

import os
import re
import pytest
import ast
import time
import functools
from playwright.sync_api import Page, Locator, expect, Error as PlaywrightTimeoutError, BrowserContext

# 全局变量，用于在测试会话结束时报告总的sleep时间
_total_sleep_time = 0.0


def _log_action(func):
    """
    装饰器，用于自动记录关键字操作的详细步骤，包括截图和状态记录。
    
    :param func: 被装饰的函数
    :return: 装饰后的函数
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # 获取self实例
        self = args[0] if args else None
        if not self or not hasattr(self, 'report_logger') or not self.report_logger:
            # 如果没有report_logger，直接执行原函数
            return func(*args, **kwargs)
        
        # 提取关键字信息
        keyword_name = func.__name__
        description = kwargs.get('描述', keyword_name)
        target = kwargs.get('目标对象', '')
        locator_type = kwargs.get('定位方式', '')
        data_content = kwargs.get('数据内容', '')
        
        # 构建详细信息
        details = {}
        if target:
            details['target'] = target
        if locator_type:
            details['locator_type'] = locator_type
        if data_content:
            details['data_content'] = data_content
        
        # 开始记录步骤
        self.report_logger.start_step(
            keyword=keyword_name,
            description=description,
            details=details
        )
        
        try:
            # 执行原函数
            result = func(*args, **kwargs)
            # 结束记录步骤（成功）
            self.report_logger.end_step('PASS')
            return result
        except Exception as e:
            # 记录失败状态
            error_msg = f"{type(e).__name__}: {str(e)}"
            self.report_logger.end_step('FAIL', error_msg)
            # 重新抛出异常，不影响测试执行
            raise
            
    return wrapper


class Keywords:
    DEFAULT_TIMEOUT = 10000

    def __init__(self, page: Page, report_logger=None):
        """
        初始化Keywords实例。
        持有整个浏览器上下文(Context)以管理多个页面，并设置初始活动页面。
        """
        self.context: BrowserContext = page.context
        self.active_page: Page = page  # 初始活动页面是主页面
        self.report_logger = report_logger  # ReportLogger实例，用于记录测试步骤
        
        # 将默认超时应用到初始页面
        self.active_page.set_default_timeout(self.DEFAULT_TIMEOUT)
        
        # 从上下文中获取运行模式
        self.mode = getattr(self.context, 'running_mode', 'headed')
        self.expect = expect
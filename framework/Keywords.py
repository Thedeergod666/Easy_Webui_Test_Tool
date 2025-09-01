# -*- coding: utf-8 -*-
"""
向后兼容模块
保持原有的导入路径 from framework.Keywords import Keywords 仍然可以正常工作
"""

# 从新的keywords模块导入所有必要的组件
from .keywords import Keywords, _log_action, _total_sleep_time

# 为了完全向后兼容，确保所有原有的导入都能正常工作
__all__ = [
    'Keywords',
    '_log_action', 
    '_total_sleep_time'
]

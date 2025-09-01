# -*- coding: utf-8 -*-
"""
模块入口文件
用于初始化keywords模块
"""

# 导入各个子模块
from .base import Keywords, _log_action, _total_sleep_time
from .page_management import PageManagementMixin
from .element_locator import ElementLocatorMixin
from .user_interaction import UserInteractionMixin
from .verification import VerificationMixin
from .test_utilities import TestUtilitiesMixin

# 通过多重继承组合各个Mixin创建统一的Keywords主类
class Keywords(Keywords, PageManagementMixin, ElementLocatorMixin,
              UserInteractionMixin, VerificationMixin, TestUtilitiesMixin):
    """统一的Keywords主类
    
    通过多重继承组合各个功能模块的Mixin类，提供完整的功能接口。
    """
    pass

# 定义模块的公共接口
__all__ = [
    'Keywords',
    '_log_action',
    '_total_sleep_time'
]
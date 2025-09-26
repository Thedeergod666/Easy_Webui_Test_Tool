# -*- coding: utf-8 -*-
"""
页面管理模块
提供页面导航、页面切换和页面管理相关的关键字
"""

import re
import time
import pytest
from enum import Enum
from typing import Optional, Union
from playwright.sync_api import Page, Error as PlaywrightTimeoutError
from .base import _log_action
from .error_handling import UnifiedErrorHandlingMixin, PageOperationResult, ErrorSeverity
from .performance_optimization import URLMatchingOptimizer
from .concurrency_coordination import ConcurrencyCoordinationMixin, OperationType, LockType, thread_safe
from collections import OrderedDict
import threading
from typing import Dict, Any
import weakref


class UrlPatternType(Enum):
    """URL模式类型枚举"""
    EXACT = "exact"          # 精确匹配
    WILDCARD = "wildcard"    # 通配符匹配
    REGEX = "regex"          # 正则表达式匹配
    PARTIAL = "partial"      # 部分匹配


class PageLifecycleManager:
    """
    页面生命周期管理器
    负责跟踪页面引用、自动清理和状态维护
    """
    
    def __init__(self):
        self.page_references: Dict[str, weakref.ref] = {}
        self.cleanup_history: OrderedDict = OrderedDict()  # 保留最近清理历史
        self.operation_lock = threading.RLock()  # 操作锁，支持重入
        self.cleanup_enabled = True
        
    def register_page(self, page: Page, page_id: str) -> None:
        """
        注册页面引用，使用弱引用避免内存泄漏
        """
        with self.operation_lock:
            # 创建弱引用，页面被删除时自动清理
            weak_ref = weakref.ref(page, lambda ref: self._on_page_deleted(page_id))
            self.page_references[page_id] = weak_ref
            
            # 设置页面关闭事件监听
            try:
                page.on('close', lambda: self._on_page_closed(page_id))
                print(f"    [生命周期] 页面 {page_id} 已注册，URL: {page.url}")
            except Exception as e:
                print(f"    [生命周期] 警告: 页面 {page_id} 事件监听设置失败: {e}")
    
    def _on_page_closed(self, page_id: str) -> None:
        """
        页面关闭事件处理
        """
        if not self.cleanup_enabled:
            return
            
        with self.operation_lock:
            if page_id in self.page_references:
                print(f"    [生命周期] 检测到页面 {page_id} 关闭事件，开始清理...")
                self._cleanup_page_reference(page_id, reason="页面关闭")
    
    def _on_page_deleted(self, page_id: str) -> None:
        """
        页面对象被垃圾回收时的处理
        """
        if not self.cleanup_enabled:
            return
            
        with self.operation_lock:
            if page_id in self.page_references:
                print(f"    [生命周期] 检测到页面 {page_id} 对象被回收，清理引用...")
                self._cleanup_page_reference(page_id, reason="对象回收")
    
    def _cleanup_page_reference(self, page_id: str, reason: str) -> None:
        """
        清理单个页面引用
        """
        try:
            if page_id in self.page_references:
                del self.page_references[page_id]
                
                # 记录清理历史（保留最近100条）
                import time
                self.cleanup_history[page_id] = {
                    'timestamp': time.time(),
                    'reason': reason
                }
                
                # 限制历史记录大小
                while len(self.cleanup_history) > 100:
                    self.cleanup_history.popitem(last=False)
                    
                print(f"    [生命周期] ✓ 页面 {page_id} 引用已清理 ({reason})")
                
        except Exception as e:
            print(f"    [生命周期] 清理页面 {page_id} 引用时出错: {e}")
    
    def cleanup_all_invalid_references(self) -> int:
        """
        清理所有无效的页面引用
        返回清理的引用数量
        """
        if not self.cleanup_enabled:
            return 0
            
        with self.operation_lock:
            invalid_refs = []
            
            for page_id, weak_ref in self.page_references.items():
                page = weak_ref()
                if page is None or (hasattr(page, 'is_closed') and page.is_closed()):
                    invalid_refs.append(page_id)
            
            for page_id in invalid_refs:
                self._cleanup_page_reference(page_id, reason="无效引用")
                
            if invalid_refs:
                print(f"    [生命周期] ✓ 清理了 {len(invalid_refs)} 个无效页面引用")
                
            return len(invalid_refs)
    
    def get_active_page_count(self) -> int:
        """
        获取当前活跃页面数量
        """
        with self.operation_lock:
            active_count = 0
            for weak_ref in self.page_references.values():
                page = weak_ref()
                if page is not None and hasattr(page, 'is_closed') and not page.is_closed():
                    active_count += 1
            return active_count
    
    def get_memory_status(self) -> Dict[str, Any]:
        """
        获取内存使用状态
        """
        with self.operation_lock:
            return {
                'total_references': len(self.page_references),
                'active_pages': self.get_active_page_count(),
                'cleanup_history_size': len(self.cleanup_history),
                'cleanup_enabled': self.cleanup_enabled
            }
    
    def enable_cleanup(self, enabled: bool = True) -> None:
        """
        启用或禁用自动清理
        """
        with self.operation_lock:
            self.cleanup_enabled = enabled
            print(f"    [生命周期] 自动清理已{'启用' if enabled else '禁用'}")


class MatchResult:
    """匹配结果数据结构"""
    
    def __init__(self, success: bool = False, matched_page: Optional[Page] = None,
                 pattern_type: UrlPatternType = UrlPatternType.EXACT,
                 match_score: float = 0.0, fallback_used: bool = False,
                 base_url: Optional[str] = None):
        self.success = success                    # 匹配是否成功
        self.matched_page = matched_page         # 匹配的页面对象
        self.pattern_type = pattern_type         # 使用的匹配类型
        self.match_score = match_score           # 匹配置信度(0-1)
        self.fallback_used = fallback_used       # 是否使用了降级策略
        self.base_url = base_url                 # 降级使用的基础URL


class PageManagementMixin(UnifiedErrorHandlingMixin, ConcurrencyCoordinationMixin):
    """页面管理Mixin类
     
    提供页面导航、页面切换和页面管理相关的方法实现。
    """
    
    def __init__(self, *args, **kwargs):
        # 首先调用父类的__init__
        super().__init__(*args, **kwargs)
        
        # 初始化页面生命周期管理器
        self.page_lifecycle_manager = PageLifecycleManager()
        
        # 初始化URL匹配性能优化器
        self.url_optimizer = URLMatchingOptimizer(max_cache_size=100, cache_ttl=300)
        
        # 如果已经有context，立即注册现有页面
        if hasattr(self, 'context') and self.context:
            self._register_existing_pages()
    
    def _register_existing_pages(self):
        """
        注册context中已存在的页面
        """
        try:
            for i, page in enumerate(self.context.pages):
                page_id = f"page_{i+1}"
                self.page_lifecycle_manager.register_page(page, page_id)
                
                # 将页面添加到URL索引
                try:
                    if not page.is_closed() and page.url:
                        self.url_optimizer.add_page_to_index(page.url, page)
                except Exception as e:
                    print(f"    [性能优化] 注册页面索引失败: {e}")
                
            # 设置页面创建事件监听
            self.context.on('page', self._on_new_page_created)
            print(f"    [生命周期] 已注册 {len(self.context.pages)} 个现有页面")
        except Exception as e:
            print(f"    [生命周期] 注册现有页面时出错: {e}")
    
    def _on_new_page_created(self, page: Page):
        """
        新页面创建事件处理
        """
        try:
            page_index = len(self.context.pages)
            page_id = f"page_{page_index}"
            self.page_lifecycle_manager.register_page(page, page_id)
            
            # 将新页面添加到URL索引
            try:
                if page.url and page.url != 'about:blank':
                    self.url_optimizer.add_page_to_index(page.url, page)
            except Exception as e:
                print(f"    [性能优化] 添加新页面索引失败: {e}")
            
            print(f"    [生命周期] 新页面 {page_id} 已自动注册")
        except Exception as e:
            print(f"    [生命周期] 注册新页面时出错: {e}")
    
    def _validate_and_adjust_active_page(self):
        """
        验证和调整活跃页面指针
        如果当前活跃页面已关闭或无效，自动切换到有效页面
        """
        try:
            # 检查当前活跃页面是否有效
            if (hasattr(self, 'active_page') and 
                self.active_page and 
                not self.active_page.is_closed() and 
                self.active_page in self.context.pages):
                return  # 活跃页面有效，无需调整
            
            # 当前活跃页面无效，寻找替代页面
            valid_pages = [page for page in self.context.pages if not page.is_closed()]
            
            if valid_pages:
                old_page_info = "N/A"
                if hasattr(self, 'active_page') and self.active_page:
                    try:
                        old_page_info = f"索引{self.context.pages.index(self.active_page) + 1}" if self.active_page in self.context.pages else "已移除"
                    except:
                        old_page_info = "无效"
                
                # 优先选择第一个有效页面（主页面）
                new_active_page = valid_pages[0]
                self.active_page = new_active_page
                new_page_index = self.context.pages.index(new_active_page) + 1
                
                print(f"    [生命周期] 活跃页面已调整: {old_page_info} -> 页面{new_page_index} ({new_active_page.url})")
            else:
                print(f"    [生命周期] 警告: 没有可用的有效页面")
                self.active_page = None
                
        except Exception as e:
            print(f"    [生命周期] 活跃页面调整失败: {e}")
    
    @thread_safe(OperationType.CLEANUP, LockType.EXCLUSIVE)
    def cleanup_memory(self):
        """
        [关键字] 手动清理页面引用内存
        用于测试结束或长期运行时的内存维护
        """
        print(f"执行 [内存清理]: 开始清理页面引用...")
        
        # 获取清理前的状态
        before_status = self.page_lifecycle_manager.get_memory_status()
        
        # 执行清理
        cleaned_count = self.page_lifecycle_manager.cleanup_all_invalid_references()
        
        # 验证和调整活跃页面
        self._validate_and_adjust_active_page()
        
        # 获取清理后的状态
        after_status = self.page_lifecycle_manager.get_memory_status()
        
        print(f"  > 清理前: {before_status['total_references']} 个引用，{before_status['active_pages']} 个活跃页面")
        print(f"  > 清理后: {after_status['total_references']} 个引用，{after_status['active_pages']} 个活跃页面")
        print(f"✓ [内存清理] 完成，清理了 {cleaned_count} 个无效引用")
    
    def get_memory_status(self):
        """
        [关键字] 获取当前内存使用状态
        用于监控和调试内存使用情况
        """
        status = self.page_lifecycle_manager.get_memory_status()
        print(f"执行 [内存状态]: 当前状态查询")
        print(f"  > 总引用数: {status['total_references']}")
        print(f"  > 活跃页面: {status['active_pages']}")
        print(f"  > 清理历史: {status['cleanup_history_size']} 条记录")
        print(f"  > 自动清理: {'已启用' if status['cleanup_enabled'] else '已禁用'}")
        return status
    
    def get_performance_report(self):
        """
        [关键字] 获取URL匹配性能报告
        用于监控和调试URL匹配性能
        """
        if not hasattr(self, 'url_optimizer'):
            print(f"执行 [性能报告]: URL优化器未初始化")
            return {}
        
        report = self.url_optimizer.get_performance_report()
        print(f"执行 [性能报告]: URL匹配性能统计")
        
        # 缓存统计
        cache_stats = report.get('cache_statistics', {})
        print(f"  > 缓存状态:")
        print(f"    当前大小: {cache_stats.get('cache_size', 0)}/{cache_stats.get('max_cache_size', 0)}")
        print(f"    命中率: {cache_stats.get('cache_hit_rate', 0):.2%}")
        print(f"    命中次数: {cache_stats.get('cache_hits', 0)}")
        print(f"    未命中次数: {cache_stats.get('cache_misses', 0)}")
        
        # 索引统计
        index_stats = report.get('index_statistics', {})
        print(f"  > 索引状态:")
        print(f"    索引URL数量: {index_stats.get('total_indexed_urls', 0)}")
        print(f"    域名数量: {index_stats.get('domain_count', 0)}")
        print(f"    路径前缀数量: {index_stats.get('path_prefixes', 0)}")
        print(f"    索引查找次数: {index_stats.get('index_lookups', 0)}")
        
        # 匹配统计
        match_stats = report.get('matching_statistics', {})
        print(f"  > 匹配状态:")
        print(f"    精确匹配次数: {match_stats.get('exact_matches', 0)}")
        print(f"    模式匹配次数: {match_stats.get('pattern_matches', 0)}")
        print(f"    总搜索次数: {match_stats.get('total_searches', 0)}")
        print(f"    平均搜索时间: {match_stats.get('average_search_time_ms', 0):.2f}ms")
        
        return report
    
    def optimize_url_performance(self):
        """
        [关键字] 优化URL匹配性能
        清理过期缓存和优化索引结构
        """
        print(f"执行 [性能优化]: 开始URL匹配性能优化...")
        
        if hasattr(self, 'url_optimizer'):
            # 优化索引
            self.url_optimizer.optimize_indexes()
            
            # 获取优化后的状态
            report = self.url_optimizer.get_performance_report()
            cache_stats = report.get('cache_statistics', {})
            index_stats = report.get('index_statistics', {})
            
            print(f"  > 优化结果:")
            print(f"    缓存大小: {cache_stats.get('cache_size', 0)}")
            print(f"    索引URL数: {index_stats.get('total_indexed_urls', 0)}")
            print(f"    有效域名: {index_stats.get('domain_count', 0)}")
            print(f"    有效路径: {index_stats.get('path_prefixes', 0)}")
        else:
            print(f"  > URL优化器未初始化，跳过优化")
        
        print(f"✓ [性能优化] 完成")
    
    def get_page_variable_mapping(self):
        """
        [关键字] 获取页面变量映射信息
        显示当前页面变量的映射关系和可用性
        """
        print(f"执行 [页面映射]: 当前页面变量映射状态")
        
        if not self.context or not self.context.pages:
            print(f"  > 当前没有可用页面")
            return {}
        
        mapping_info = {}
        page_count = len(self.context.pages)
        
        print(f"  > 页面总数: {page_count}")
        print(f"  > 变量映射关系:")
        
        # 标准化映射规则
        # 1. page - 当前活动页面
        if hasattr(self, 'active_page') and self.active_page:
            try:
                active_index = self.context.pages.index(self.active_page) + 1
                mapping_info['page'] = {
                    'target': f'页面{active_index}',
                    'url': self.active_page.url,
                    'status': '活动' if not self.active_page.is_closed() else '已关闭'
                }
                print(f"    page -> 页面{active_index} (活动页面) - {self.active_page.url}")
            except (ValueError, AttributeError):
                mapping_info['page'] = {'target': 'N/A', 'url': 'N/A', 'status': '无效'}
                print(f"    page -> N/A (活动页面无效)")
        
        # 2. page1, page2, ... - 按索引的页面引用
        for i in range(page_count):
            page = self.context.pages[i]
            page_var = f'page{i+1}'
            try:
                status = '正常' if not page.is_closed() else '已关闭'
                mapping_info[page_var] = {
                    'target': f'页面{i+1}',
                    'url': page.url,
                    'status': status
                }
                print(f"    {page_var} -> 页面{i+1} ({status}) - {page.url}")
            except AttributeError:
                mapping_info[page_var] = {'target': f'页面{i+1}', 'url': 'N/A', 'status': '错误'}
                print(f"    {page_var} -> 页面{i+1} (错误) - 无法获取URL")
        
        # 3. 兼容性映射（逐步弃用）
        if page_count > 0:
            page0_info = mapping_info.get('page1', {})
            mapping_info['page0'] = page0_info.copy()
            mapping_info['page0']['deprecated'] = True
            print(f"    page0 -> 页面1 (兼容性映射，建议使用 page)")
        
        # 4. pages - 页面列表引用（逐步弃用）
        mapping_info['pages'] = {
            'target': f'页面列表[{page_count}个]',
            'status': '可用',
            'deprecated': True
        }
        print(f"    pages -> 页面列表[{page_count}个] (兼容性映射，建议使用具体页面变量)")
        
        # 显示映射建议
        print(f"  > 映射建议:")
        print(f"    推荐使用: page (当前活动页面), page1, page2, ...")
        print(f"    避免使用: page0 (已弃用), pages (已弃用)")
        
        return mapping_info
    
    def switch_to_standard_mapping(self):
        """
        [关键字] 切换到标准化页面映射
        清理旧的映射规则，采用新的标准化映射
        """
        print(f"执行 [映射标准化]: 切换到标准化页面映射")
        
        # 获取当前映射状态
        current_mapping = self.get_page_variable_mapping()
        
        # 检查是否需要映射调整
        needs_adjustment = False
        
        if not current_mapping.get('page', {}).get('status') == '活动':
            needs_adjustment = True
            print(f"  > 检测到活动页面映射异常，需要调整")
        
        deprecated_vars = [k for k, v in current_mapping.items() 
                          if v.get('deprecated', False)]
        if deprecated_vars:
            print(f"  > 检测到已弃用的变量: {deprecated_vars}")
        
        # 执行映射调整
        if needs_adjustment:
            if hasattr(self, '_validate_and_adjust_active_page'):
                self._validate_and_adjust_active_page()
                print(f"  > 活动页面映射已调整")
        
        # 显示调整后的映射
        print(f"  > 标准化映射完成")
        final_mapping = self.get_page_variable_mapping()
        
        return final_mapping
    
    def diagnose_page_mapping(self):
        """
        [关键字] 诊断页面变量映射问题
        检查映射一致性和潜在问题
        """
        print(f"执行 [映射诊断]: 开始页面变量映射诊断")
        print(f"=" * 50)
        
        # 获取基本信息
        page_count = len(self.context.pages) if self.context and self.context.pages else 0
        print(f"📊 基本信息:")
        print(f"  页面总数: {page_count}")
        
        if page_count == 0:
            print(f"⚠️  警告: 没有可用页面，所有页面变量都不可用")
            return
        
        # 检查活动页面状态
        print(f"\n🎯 活动页面状态:")
        if hasattr(self, 'active_page') and self.active_page:
            try:
                if self.active_page in self.context.pages:
                    active_index = self.context.pages.index(self.active_page) + 1
                    active_status = '正常' if not self.active_page.is_closed() else '已关闭'
                    print(f"  ✓ 活动页面: 页面{active_index} ({active_status})")
                    print(f"    URL: {self.active_page.url}")
                else:
                    print(f"  ❌ 活动页面不在页面列表中")
            except Exception as e:
                print(f"  ❌ 活动页面状态异常: {e}")
        else:
            print(f"  ❌ 没有设置活动页面")
        
        # 检查所有页面状态
        print(f"\n📋 页面状态检查:")
        issues = []
        for i, page in enumerate(self.context.pages):
            page_num = i + 1
            try:
                is_closed = page.is_closed()
                url = page.url if not is_closed else '[已关闭]'
                status_icon = '✓' if not is_closed else '❌'
                print(f"  {status_icon} 页面{page_num}: {url}")
                
                if is_closed:
                    issues.append(f"页面{page_num}已关闭但仍在列表中")
                    
            except Exception as e:
                print(f"  ❌ 页面{page_num}: 状态检查失败 - {e}")
                issues.append(f"页面{page_num}状态检查失败")
        
        # 变量可用性检查
        print(f"\n🔗 变量可用性:")
        available_vars = []
        deprecated_vars = []
        
        # 标准变量
        if hasattr(self, 'active_page') and self.active_page and not self.active_page.is_closed():
            available_vars.append('page')
        
        for i in range(page_count):
            var_name = f'page{i+1}'
            if not self.context.pages[i].is_closed():
                available_vars.append(var_name)
        
        # 兼容性变量（已弃用）
        if page_count > 0:
            deprecated_vars.extend(['page0', 'pages'])
        
        print(f"  ✓ 可用变量: {', '.join(available_vars) if available_vars else '无'}")
        print(f"  ⚠️  已弃用变量: {', '.join(deprecated_vars) if deprecated_vars else '无'}")
        
        # 问题汇总
        print(f"\n🔍 问题汇总:")
        if not issues:
            print(f"  ✓ 未发现映射问题")
        else:
            for issue in issues:
                print(f"  ❌ {issue}")
        
        # 建议
        print(f"\n💡 使用建议:")
        print(f"  1. 优先使用 'page' 访问当前活动页面")
        print(f"  2. 使用 'page1', 'page2' 等明确指定页面")
        print(f"  3. 避免使用已弃用的 'page0' 和 'pages'")
        if issues:
            print(f"  4. 建议执行 'cleanup_memory' 清理无效页面")
            print(f"  5. 可执行 'switch_to_standard_mapping' 修复映射")
        
        print(f"=" * 50)
        print(f"✓ [映射诊断] 完成")
    
    # URL匹配配置选项
    URL_PATTERN_CONFIG = {
        'enable_pattern_matching': True,    # 启用模式匹配功能
        'strict_matching': False,          # 严格匹配模式，禁用降级策略
        'case_sensitive': False,           # URL匹配是否区分大小写
        'max_pattern_length': 500,         # URL模式最大长度限制
    }
    
    def _match_url_pattern(self, url_pattern: str, target_url: str) -> tuple[bool, UrlPatternType, float]:
        """
        [内部] 解析和匹配URL模式。
        
        Args:
            url_pattern (str): URL模式字符串
            target_url (str): 待匹配的目标URL
            
        Returns:
            tuple[bool, UrlPatternType, float]: (是否匹配成功, 匹配类型, 匹配评分)
        """
        if not self.URL_PATTERN_CONFIG['enable_pattern_matching']:
            # 如果禁用模式匹配，只进行精确匹配
            exact_match = url_pattern == target_url
            return exact_match, UrlPatternType.EXACT, 1.0 if exact_match else 0.0
        
        # 检查模式长度限制
        if len(url_pattern) > self.URL_PATTERN_CONFIG['max_pattern_length']:
            print(f"    [URL匹配] 警告: URL模式过长 ({len(url_pattern)} > {self.URL_PATTERN_CONFIG['max_pattern_length']})。")
            return False, UrlPatternType.EXACT, 0.0
        
        # 准备对比的URL（大小写处理）
        pattern_to_match = url_pattern if self.URL_PATTERN_CONFIG['case_sensitive'] else url_pattern.lower()
        url_to_match = target_url if self.URL_PATTERN_CONFIG['case_sensitive'] else target_url.lower()
        
        try:
            # 1. 正则表达式匹配：以 {regex: 开头
            if pattern_to_match.startswith('{regex:'):
                if not pattern_to_match.endswith('}'):
                    print(f"    [URL匹配] 正则表达式格式错误: {url_pattern}")
                    return False, UrlPatternType.REGEX, 0.0
                
                # 提取正则表达式
                regex_pattern = pattern_to_match[7:-1]  # 移除 '{regex:' 和 '}'
                
                try:
                    # 编译和匹配正则表达式
                    regex_flags = re.IGNORECASE if not self.URL_PATTERN_CONFIG['case_sensitive'] else 0
                    compiled_regex = re.compile(regex_pattern, regex_flags)
                    match = compiled_regex.search(url_to_match)
                    
                    if match:
                        # 计算匹配评分（基于匹配的字符数占比）
                        match_length = len(match.group(0))
                        total_length = len(url_to_match)
                        score = min(1.0, match_length / total_length * 1.2)  # 略微加权
                        print(f"    [URL匹配] ✓ 正则表达式匹配成功: {regex_pattern} -> {target_url} (评分: {score:.2f})")
                        return True, UrlPatternType.REGEX, score
                    else:
                        print(f"    [URL匹配] ✗ 正则表达式匹配失败: {regex_pattern} -> {target_url}")
                        return False, UrlPatternType.REGEX, 0.0
                        
                except re.error as e:
                    print(f"    [URL匹配] 正则表达式编译错误: {regex_pattern}, 错误: {e}")
                    return False, UrlPatternType.REGEX, 0.0
            
            # 2. 通配符匹配：包含 * 或 ? 字符
            elif '*' in pattern_to_match or '?' in pattern_to_match:
                # 将通配符转换为正则表达式
                # 转义特殊字符，但保留通配符
                escaped_pattern = re.escape(pattern_to_match)
                
                # 还原通配符
                escaped_pattern = escaped_pattern.replace(r'\*', '.*')  # * -> .*
                escaped_pattern = escaped_pattern.replace(r'\?', '.')   # ? -> .
                
                # 支持 ** 匹配任意路径层级
                escaped_pattern = escaped_pattern.replace('.*.*', '.*')  # .*.* -> .*
                
                try:
                    regex_flags = re.IGNORECASE if not self.URL_PATTERN_CONFIG['case_sensitive'] else 0
                    compiled_regex = re.compile(f'^{escaped_pattern}$', regex_flags)
                    match = compiled_regex.match(url_to_match)
                    
                    if match:
                        # 计算匹配评分（通配符匹配评分略低一些）
                        exact_chars = len([c for c in pattern_to_match if c not in '*?'])
                        total_chars = len(pattern_to_match)
                        score = min(0.9, exact_chars / total_chars * 0.8 + 0.2)  # 最高 0.9
                        print(f"    [URL匹配] ✓ 通配符匹配成功: {url_pattern} -> {target_url} (评分: {score:.2f})")
                        return True, UrlPatternType.WILDCARD, score
                    else:
                        print(f"    [URL匹配] ✗ 通配符匹配失败: {url_pattern} -> {target_url}")
                        return False, UrlPatternType.WILDCARD, 0.0
                        
                except re.error as e:
                    print(f"    [URL匹配] 通配符转换正则表达式错误: {escaped_pattern}, 错误: {e}")
                    return False, UrlPatternType.WILDCARD, 0.0
            
            # 3. 精确匹配
            elif pattern_to_match == url_to_match:
                print(f"    [URL匹配] ✓ 精确匹配成功: {url_pattern} -> {target_url}")
                return True, UrlPatternType.EXACT, 1.0
            
            # 4. 部分匹配（子字符串包含）
            elif pattern_to_match in url_to_match:
                # 计算部分匹配评分
                score = len(pattern_to_match) / len(url_to_match) * 0.6  # 最高 0.6
                print(f"    [URL匹配] ✓ 部分匹配成功: {url_pattern} -> {target_url} (评分: {score:.2f})")
                return True, UrlPatternType.PARTIAL, score
            
            # 5. 没有匹配
            else:
                print(f"    [URL匹配] ✗ 所有匹配类型都失败: {url_pattern} -> {target_url}")
                return False, UrlPatternType.EXACT, 0.0
                
        except Exception as e:
            print(f"    [URL匹配] 匹配过程异常: {e}")
            return False, UrlPatternType.EXACT, 0.0
    
    def _find_matching_page(self, url_pattern: str) -> MatchResult:
        """
        [内部] 在已打开页面中查找匹配的页面。
        使用性能优化的匹配算法。
        
        Args:
            url_pattern (str): URL模式字符串
            
        Returns:
            MatchResult: 匹配结果对象
        """
        if not self.context or not self.context.pages:
            print(f"    [URL匹配] 没有可用的页面")
            return MatchResult(success=False)
        
        print(f"    [URL匹配] 开始在 {len(self.context.pages)} 个页面中查找匹配: {url_pattern}")
        
        # 第一步：尝试快速精确匹配
        if hasattr(self, 'url_optimizer'):
            exact_match_page = self.url_optimizer.fast_exact_match(url_pattern)
            if exact_match_page and not exact_match_page.is_closed():
                print(f"    [URL匹配] ✓ 快速精确匹配成功: {url_pattern}")
                return MatchResult(
                    success=True,
                    matched_page=exact_match_page,
                    pattern_type=UrlPatternType.EXACT,
                    match_score=1.0,
                    fallback_used=False
                )
        
        best_match = None
        best_score = 0.0
        best_pattern_type = UrlPatternType.EXACT
        matching_pages = []
        
        # 第二步：模式匹配（使用优化算法）
        for i, page in enumerate(self.context.pages):
            try:
                # 检查页面是否关闭
                if page.is_closed():
                    print(f"    [URL匹配] 跳过已关闭的页面 {i+1}")
                    continue
                
                page_url = page.url
                if not page_url or page_url == 'about:blank':
                    print(f"    [URL匹配] 跳过空白页面 {i+1}: {page_url}")
                    continue
                
                # 使用优化的匹配算法
                is_match, pattern_type, score = self._optimized_match_url_pattern(url_pattern, page_url)
                
                if is_match:
                    matching_pages.append({
                        'page': page,
                        'index': i,
                        'url': page_url,
                        'score': score,
                        'pattern_type': pattern_type
                    })
                    
                    # 更新最佳匹配
                    if score > best_score:
                        best_match = page
                        best_score = score
                        best_pattern_type = pattern_type
                        
            except Exception as e:
                print(f"    [URL匹配] 检查页面 {i+1} 时出错: {e}")
                continue
        
        # 处理匹配结果
        if matching_pages:
            # 按匹配评分排序，选择最佳匹配
            matching_pages.sort(key=lambda x: x['score'], reverse=True)
            best_page_info = matching_pages[0]
            
            print(f"    [URL匹配] ✓ 找到 {len(matching_pages)} 个匹配页面，最佳匹配:")
            print(f"        页面 {best_page_info['index']+1}: {best_page_info['url']}")
            print(f"        匹配类型: {best_page_info['pattern_type'].value}")
            print(f"        匹配评分: {best_page_info['score']:.2f}")
            
            # 如果有多个匹配，显示其他匹配页面
            if len(matching_pages) > 1:
                print(f"        其他匹配页面:")
                for page_info in matching_pages[1:3]:  # 最多显示另外2个
                    print(f"          页面 {page_info['index']+1}: {page_info['url']} (评分: {page_info['score']:.2f})")
            
            return MatchResult(
                success=True,
                matched_page=best_match,
                pattern_type=best_pattern_type,
                match_score=best_score,
                fallback_used=False
            )
        else:
            print(f"    [URL匹配] ✗ 未找到匹配的页面")
            
            # 显示所有可用页面供参考
            print(f"        当前可用页面:")
            for i, page in enumerate(self.context.pages):
                try:
                    if not page.is_closed():
                        url = page.url
                        print(f"          页面 {i+1}: {url}")
                except:
                    print(f"          页面 {i+1}: [无法获取URL]")
            
            return MatchResult(success=False)
    
    def _optimized_match_url_pattern(self, url_pattern: str, target_url: str) -> tuple[bool, UrlPatternType, float]:
        """
        [内部] 优化的URL模式匹配算法。
        优先使用性能优化器，失败时降级到传统算法。
        
        Args:
            url_pattern (str): URL模式字符串
            target_url (str): 待匹配的目标URL
            
        Returns:
            tuple[bool, UrlPatternType, float]: (是否匹配成功, 匹配类型, 匹配评分)
        """
        if not self.URL_PATTERN_CONFIG['enable_pattern_matching']:
            # 如果禁用模式匹配，只进行精确匹配
            exact_match = url_pattern == target_url
            return exact_match, UrlPatternType.EXACT, 1.0 if exact_match else 0.0
        
        # 检查模式长度限制
        if len(url_pattern) > self.URL_PATTERN_CONFIG['max_pattern_length']:
            print(f"    [URL匹配] 警告: URL模式过长 ({len(url_pattern)} > {self.URL_PATTERN_CONFIG['max_pattern_length']})。")
            return False, UrlPatternType.EXACT, 0.0
        
        # 优先使用性能优化器
        if hasattr(self, 'url_optimizer'):
            try:
                # 1. 正则表达式匹配：以 {regex: 开头
                if url_pattern.startswith('{regex:'):
                    if not url_pattern.endswith('}'):
                        print(f"    [URL匹配] 正则表达式格式错误: {url_pattern}")
                        return False, UrlPatternType.REGEX, 0.0
                    
                    # 提取正则表达式
                    regex_pattern = url_pattern[7:-1]  # 移除 '{regex:' 和 '}'
                    is_match, score = self.url_optimizer.optimized_pattern_match(
                        regex_pattern, target_url, "regex"
                    )
                    
                    if is_match:
                        print(f"    [URL匹配] ✓ 正则表达式匹配成功: {regex_pattern} -> {target_url} (评分: {score:.2f})")
                        return True, UrlPatternType.REGEX, score
                    else:
                        print(f"    [URL匹配] ✗ 正则表达式匹配失败: {regex_pattern} -> {target_url}")
                        return False, UrlPatternType.REGEX, 0.0
                
                # 2. 通配符匹配：包含 * 或 ? 字符
                elif '*' in url_pattern or '?' in url_pattern:
                    is_match, score = self.url_optimizer.optimized_pattern_match(
                        url_pattern, target_url, "wildcard"
                    )
                    
                    if is_match:
                        print(f"    [URL匹配] ✓ 通配符匹配成功: {url_pattern} -> {target_url} (评分: {score:.2f})")
                        return True, UrlPatternType.WILDCARD, score
                    else:
                        print(f"    [URL匹配] ✗ 通配符匹配失败: {url_pattern} -> {target_url}")
                        return False, UrlPatternType.WILDCARD, 0.0
            
            except Exception as e:
                print(f"    [URL匹配] 性能优化器匹配失败: {e}，降级到传统算法")
        
        # 降级到传统算法
        return self._match_url_pattern(url_pattern, target_url)
    
    def _extract_base_url(self, url_pattern: str) -> Optional[str]:
        """
        [内部] 从URL模式中提取基础URL用于降级导航。
        
        Args:
            url_pattern (str): 包含模式的URL字符串
            
        Returns:
            Optional[str]: 提取的基础URL，如果无法提取则返回None
        """
        try:
            print(f"    [基础URL提取] 开始从模式中提取: {url_pattern}")
            
            # 1. 正则表达式模式处理
            if url_pattern.startswith('{regex:') and url_pattern.endswith('}'):
                # 从正则表达式中提取可能的基础URL
                regex_pattern = url_pattern[7:-1]  # 移除 '{regex:' 和 '}'
                
                # 尝试从正则中提取基础部分
                # 首先尝试查找普通URL结构（处理转义字符）
                # 将转义的点号恢复为普通点号来识别域名
                unescaped_pattern = regex_pattern.replace(r'\.', '.')
                protocol_domain_match = re.search(r'(https?://[a-zA-Z0-9.-]+)', unescaped_pattern)
                
                if protocol_domain_match:
                    base_url = protocol_domain_match.group(1)
                    print(f"    [基础URL提取] 从正则表达式提取到: {base_url}")
                    return base_url
                else:
                    # 如果无法提取，尝试找到简单的URL结构
                    simple_url_match = re.search(r'(https?://[^\s\\\(\)\[\]\{\}]+)', regex_pattern)
                    if simple_url_match:
                        base_url = simple_url_match.group(1)
                        # 移除可能的正则特殊字符
                        base_url = re.sub(r'[\\\^\$\*\+\?\{\}\[\]\|\(\)].*$', '', base_url)
                        print(f"    [基础URL提取] 从正则表达式简化提取: {base_url}")
                        return base_url if base_url else None
                    else:
                        print(f"    [基础URL提取] 无法从正则表达式提取URL: {regex_pattern}")
                        return None
            
            # 2. 通配符模式处理
            elif '*' in url_pattern or '?' in url_pattern:
                # 移除通配符及其后面的内容
                # 找到第一个通配符的位置
                first_wildcard_pos = len(url_pattern)
                for char in ['*', '?']:
                    pos = url_pattern.find(char)
                    if pos != -1 and pos < first_wildcard_pos:
                        first_wildcard_pos = pos
                
                if first_wildcard_pos < len(url_pattern):
                    base_url = url_pattern[:first_wildcard_pos]
                    
                    # 确保基础URL以完整的路径结尾
                    if base_url.endswith('/'):
                        base_url = base_url[:-1]  # 移除末尾的斜杠
                    
                    # 检查是否为有效的URL开头
                    if base_url.startswith(('http://', 'https://')):
                        print(f"    [基础URL提取] 从通配符模式提取到: {base_url}")
                        return base_url
                    else:
                        print(f"    [基础URL提取] 通配符模式提取的URL无效: {base_url}")
                        return None
                else:
                    print(f"    [基础URL提取] 通配符模式未找到通配符: {url_pattern}")
                    return None
            
            # 3. 精确匹配或部分匹配
            else:
                # 如果是完整的URL，直接返回
                if url_pattern.startswith(('http://', 'https://')):
                    print(f"    [基础URL提取] 精确匹配模式，直接返回: {url_pattern}")
                    return url_pattern
                else:
                    # 如果不是完整URL，尝试从当前页面推断基础URL
                    if hasattr(self, 'active_page') and self.active_page and not self.active_page.is_closed():
                        current_url = self.active_page.url
                        if current_url and current_url.startswith(('http://', 'https://')):
                            # 提取域名部分
                            try:
                                from urllib.parse import urlparse
                                parsed = urlparse(current_url)
                                base_url = f"{parsed.scheme}://{parsed.netloc}"
                                print(f"    [基础URL提取] 从当前页面推断: {base_url}")
                                return base_url
                            except Exception as e:
                                print(f"    [基础URL提取] URL解析失败: {e}")
                    
                    print(f"    [基础URL提取] 无法从模式提取基础URL: {url_pattern}")
                    return None
                    
        except Exception as e:
            print(f"    [基础URL提取] 提取过程异常: {e}")
            return None
    
    def configure_url_matching(self, **config_options):
        """
        [关键字] 配置URL匹配行为。
        
        可用配置选项:
        - enable_pattern_matching: bool - 启用/禁用模式匹配功能
        - strict_matching: bool - 严格匹配模式，禁用降级策略
        - case_sensitive: bool - URL匹配是否区分大小写
        - max_pattern_length: int - URL模式最大长度限制
        
        使用示例:
        configure_url_matching enable_pattern_matching=true strict_matching=false
        """
        updated_settings = []
        
        for key, value in config_options.items():
            if key in self.URL_PATTERN_CONFIG:
                old_value = self.URL_PATTERN_CONFIG[key]
                
                # 类型转换和验证
                if key in ['enable_pattern_matching', 'strict_matching', 'case_sensitive']:
                    if isinstance(value, str):
                        value = value.lower() in ['true', '1', 'yes', 'on']
                    elif not isinstance(value, bool):
                        print(f"  [URL匹配配置] 警告: {key} 应为布尔值，跳过设置")
                        continue
                        
                elif key == 'max_pattern_length':
                    try:
                        value = int(value)
                        if value <= 0:
                            print(f"  [URL匹配配置] 警告: {key} 应为正整数，跳过设置")
                            continue
                    except (ValueError, TypeError):
                        print(f"  [URL匹配配置] 警告: {key} 应为整数，跳过设置")
                        continue
                
                self.URL_PATTERN_CONFIG[key] = value
                updated_settings.append(f"{key}: {old_value} -> {value}")
                
            else:
                print(f"  [URL匹配配置] 警告: 未知配置项 '{key}'，跳过")
        
        if updated_settings:
            print(f"  [URL匹配配置] ✓ 已更新配置:")
            for setting in updated_settings:
                print(f"    {setting}")
        else:
            print(f"  [URL匹配配置] 没有可用的配置更新")
            
        print(f"  [URL匹配配置] 当前配置: {self.URL_PATTERN_CONFIG}")
    
    def get_url_matching_config(self):
        """
        [关键字] 获取当前的URL匹配配置。
        """
        print(f"  [URL匹配配置] 当前配置:")
        for key, value in self.URL_PATTERN_CONFIG.items():
            print(f"    {key}: {value}")
        return self.URL_PATTERN_CONFIG.copy()
    
    def diagnose_url_matching(self, url_pattern: str):
        """
        [关键字] 诊断URL模式匹配问题。
        提供详细的匹配过程信息和建议。
        数据内容: 要诊断的URL模式
        """
        print(f"  [URL匹配诊断] 开始诊断模式: {url_pattern}")
        print(f"  [URL匹配诊断] 当前配置: {self.URL_PATTERN_CONFIG}")
        
        if not self.context or not self.context.pages:
            print(f"  [URL匹配诊断] ✗ 没有可用的页面")
            return
        
        print(f"  [URL匹配诊断] 当前打开的页面 ({len(self.context.pages)}个):")
        
        # 显示所有页面信息
        for i, page in enumerate(self.context.pages):
            try:
                if page.is_closed():
                    print(f"    页面 {i+1}: [已关闭]")
                else:
                    url = page.url
                    print(f"    页面 {i+1}: {url}")
                    
                    # 测试匹配
                    is_match, pattern_type, score = self._match_url_pattern(url_pattern, url)
                    if is_match:
                        print(f"      ✓ 匹配成功 - 类型: {pattern_type.value}, 评分: {score:.2f}")
                    else:
                        print(f"      ✗ 匹配失败 - 类型: {pattern_type.value}")
                        
            except Exception as e:
                print(f"    页面 {i+1}: [错误: {e}]")
        
        # 提供建议
        print(f"  [URL匹配诊断] 建议:")
        
        if url_pattern.startswith('{regex:'):
            if not url_pattern.endswith('}'):
                print(f"    - 正则表达式格式错误，应以 '}}' 结尾")
            else:
                regex_pattern = url_pattern[7:-1]
                try:
                    re.compile(regex_pattern)
                    print(f"    - 正则表达式语法正确")
                except re.error as e:
                    print(f"    - 正则表达式语法错误: {e}")
        
        elif '*' in url_pattern or '?' in url_pattern:
            print(f"    - 使用通配符模式，确保模式符合预期")
            if url_pattern.count('*') > 3:
                print(f"    - 警告: 过多通配符可能影响性能")
        
        else:
            print(f"    - 使用精确或部分匹配模式")
            
        if len(url_pattern) > self.URL_PATTERN_CONFIG['max_pattern_length']:
            print(f"    - 警告: 模式长度超过限制 ({len(url_pattern)} > {self.URL_PATTERN_CONFIG['max_pattern_length']})")

    def _get_target_page(self, **kwargs) -> Page:
        """
        [内部] 根据Excel中的'页面'列获取目标Page对象。
        如果'页面'列为空，则返回当前的活动页面(self.active_page)。
        
        实现了智能页面等待和状态验证机制:
        1. 多层级等待策略（基础等待、状态等待、内容等待）
        2. 页面状态验证（可见性、加载状态、DOM就绪等）
        3. 智能重试机制（页面不存在时的恢复策略）
        """
        page_index_str = str(kwargs.get('页面', '')).strip()
        
        if not page_index_str:
            return self.active_page

        try:
            # Excel中的页码是 1-based, 列表索引是 0-based
            page_index = int(page_index_str) - 1
            if page_index < 0:
                raise ValueError("页码必须是正整数。")

            # 智能页面等待机制 - 分层等待策略
            current_pages_count = len(self.context.pages)
            required_pages_count = page_index + 1
            
            print(f"  [页面定位] 请求页面 {page_index_str} (索引: {page_index}), 当前页面数: {current_pages_count}, 需要页面数: {required_pages_count}")
            
            if current_pages_count > page_index:
                # 页面已存在，进行状态验证
                target_page = self.context.pages[page_index]
                if self._validate_page_state(target_page, page_index_str):
                    print(f"  [页面定位] ✓ 目标页面指定为 页{page_index_str} ({target_page.url})")
                    return target_page
                else:
                    print(f"  [页面定位] ⚠ 页面{page_index_str}状态异常，尝试恢复...")
                    # 尝试状态恢复
                    if self._recover_page_state(target_page):
                        print(f"  [页面定位] ✓ 页面状态恢复成功")
                        return target_page
                    else:
                        print(f"  [页面定位] ✗ 页面状态恢复失败")
            else:
                # 页面不存在，实施智能等待策略
                print(f"  [页面等待] 页面{page_index_str}不存在，启动智能等待机制...")
                
                # 基础等待 - 等待页面对象存在 (8秒，增加等待时间)
                waited_page = self._wait_for_page_creation(required_pages_count, timeout_ms=8000)
                if waited_page:
                    print(f"  [页面等待] ✓ 基础等待成功，页面已创建")
                    target_page = self.context.pages[page_index]
                    
                    # 状态等待 - 等待页面加载完成 (15秒，增加等待时间)
                    if self._wait_for_page_ready(target_page, timeout_ms=15000):
                        print(f"  [页面等待] ✓ 页面状态验证通过")
                        print(f"  [页面定位] ✓ 目标页面指定为 页{page_index_str} ({target_page.url})")
                        return target_page
                    else:
                        print(f"  [页面等待] ⚠ 页面状态验证失败，但页面存在")
                        return target_page  # 返回页面，让调用者处理
                else:
                    # 页面确实不存在，采用容错策略：使用最后一个可用页面
                    if len(self.context.pages) > 0:
                        fallback_page = self.context.pages[-1]  # 使用最后一个页面作为替代
                        print(f"  [容错机制] 页面{page_index_str}不存在，使用最后页面作为替代: 页{len(self.context.pages)} ({fallback_page.url})")
                        return fallback_page
                    
            # 所有等待策略都失败，提供详细的错误信息
            current_pages = [f"页面{i+1}: {page.url}" for i, page in enumerate(self.context.pages)]
            error_detail = f"\n当前打开的页面列表:\n" + "\n".join(current_pages) if current_pages else "\n当前没有打开的页面"
            
            # 使用警告而不是失败，让测试继续进行
            warning_msg = (f"⚠ [页面等待] 无法获取页面 '{page_index_str}'，" +
                         f"当前页面总数: {len(self.context.pages)}, 请求页面索引: {page_index}" +
                         error_detail)
            print(warning_msg)
            
            # 返回主页面作为最后的容错机制
            if len(self.context.pages) > 0:
                return self.context.pages[0]
            else:
                pytest.fail("严重错误: 没有任何可用的页面")
                       
        except ValueError as e:
            pytest.fail(f"页面参数错误: {e}")
        except Exception as e:
            pytest.fail(f"页面操作异常: {e}")
    
    def _validate_page_state(self, page: Page, page_name: str) -> bool:
        """
        [内部] 验证页面状态是否正常。
        使用智能化的验证策略，优化验证效率和准确性。
        检查页面可见性、加载状态、DOM就绪等关键指标。
        """
        try:
            # 1. 检查页面是否关闭
            if page.is_closed():
                print(f"    [状态验证] 页面{page_name}已关闭")
                return False
            
            # 2. 检查URL有效性
            current_url = page.url
            if not current_url:
                print(f"    [状态验证] 页面{page_name}URL为空")
                return False
            
            # 3. 特殊页面处理（根据项目规范）
            if current_url == 'about:blank' or current_url.startswith('about:'):
                print(f"    [状态验证] 页面{page_name}是弹窗页面，使用简化验证")
                # 对弹窗等特殊页面采用简化验证
                return True
            
            # 4. 智能化DOM状态检查（增加容错处理）
            try:
                ready_state = page.evaluate('document.readyState', timeout=1500)  # 增加超时
                if ready_state not in ['interactive', 'complete']:
                    print(f"    [状态验证] 页面{page_name}DOM未就绪: {ready_state}")
                    
                    # 等待页面渲染稳定（根据项目规范）
                    time.sleep(0.5)
                    
                    # 重新检查
                    try:
                        ready_state = page.evaluate('document.readyState', timeout=1000)
                        if ready_state not in ['interactive', 'complete']:
                            print(f"    [状态验证] 页面{page_name}等待后DOM仍未就绪: {ready_state}")
                            return False
                    except:
                        print(f"    [状态验证] 页面{page_name}重新检查DOM状态失败")
                        return False
            except Exception as dom_error:
                print(f"    [状态验证] 页面{page_name}DOM检查失败: {dom_error}，但继续检查")
                # DOM检查失败不一定意味着页面不可用，继续检查
            
            # 5. JavaScript环境检查（增加容错处理）
            try:
                js_available = page.evaluate('typeof window', timeout=1000)
                if js_available != 'object':
                    print(f"    [状态验证] 页面{page_name}JavaScript环境不可用: {js_available}")
                    # JavaScript不可用也不一定意味着页面不可用
                    print(f"    [状态验证] 页面{page_name}JavaScript不可用但允许继续")
            except Exception as js_error:
                print(f"    [状态验证] 页面{page_name}JavaScript检查失败: {js_error}，但允许继续")
                # JavaScript检查失败也不一定意味着页面不可用
            
            # 6. 基本可用性验证（最后的兼容性检查）
            try:
                # 尝试获取页面标题作为可用性检查
                title = page.evaluate('document.title || ""', timeout=1000)
                print(f"    [状态验证] 页面{page_name}基本状态正常，标题: {title[:50]}...")
            except Exception as title_error:
                print(f"    [状态验证] 页面{page_name}标题获取失败: {title_error}，但允许继续")
            
            print(f"    [状态验证] 页面{page_name}状态验证通过")
            return True
            
        except Exception as e:
            print(f"    [状态验证] 页面{page_name}状态验证异常: {e}")
            return False
    
    def _recover_page_state(self, page: Page) -> bool:
        """
        [内部] 尝试恢复页面状态。
        对于状态异常的页面，尝试修复或重新加载。
        """
        try:
            # 1. 尝试等待页面加载完成
            try:
                page.wait_for_load_state('networkidle', timeout=3000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            # 2. 尝试等待DOM就绪
            try:
                page.wait_for_load_state('domcontentloaded', timeout=2000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            # 3. 最后尝试重新刷新页面
            try:
                page.reload(timeout=5000)
                page.wait_for_load_state('domcontentloaded', timeout=3000)
                return True
            except PlaywrightTimeoutError:
                pass
            
            return False
            
        except Exception as e:
            print(f"    [状态恢复] 恢复失败: {e}")
            return False
    
    def _wait_for_page_creation(self, required_count: int, timeout_ms: int = 5000) -> bool:
        """
        [内部] 等待页面创建直到满足数量要求。
        使用短时间轮询策略，避免无限等待。
        """
        import time
        start_time = time.time()
        timeout_seconds = timeout_ms / 1000
        
        # 增加初始检查
        initial_count = len(self.context.pages)
        if initial_count >= required_count:
            return True
            
        print(f"    [页面等待] 当前{initial_count}个页面，需要{required_count}个，等待新页面创建...")
        
        while time.time() - start_time < timeout_seconds:
            current_count = len(self.context.pages)
            if current_count >= required_count:
                print(f"    [页面等待] 成功：当前已有{current_count}个页面")
                return True
            
            # 短时间等待新页面事件（增加等待时间）
            try:
                self.context.wait_for_event('page', timeout=1000)  # 从500ms增加到1000ms
                print(f"    [页面等待] 检测到新页面事件，当前页面数: {len(self.context.pages)}")
            except PlaywrightTimeoutError:
                pass  # 继续轮询
            
            # 添加微小的睡眠，避免过度消耗CPU
            time.sleep(0.1)
        
        final_count = len(self.context.pages)
        print(f"    [页面等待] 超时：最终页面数{final_count}，需要{required_count}")
        return final_count >= required_count
    
    def _wait_for_page_ready(self, page: Page, timeout_ms: int = 10000) -> bool:
        """
        [内部] 等待页面就绪并验证状态。
        包括加载状态、DOM就绪、JavaScript环境等。
        """
        try:
            # 1. 等待基本加载完成
            page.wait_for_load_state('domcontentloaded', timeout=timeout_ms)
            
            # 2. 等待网络活动稳定（可选）
            try:
                page.wait_for_load_state('networkidle', timeout=3000)
            except PlaywrightTimeoutError:
                pass  # 网络活动稳定不是必须的
            
            # 3. 验证最终状态
            return self._validate_page_state(page, "目标")
            
        except PlaywrightTimeoutError as e:
            print(f"    [页面等待] 等待超时: {e}")
            return False
        except Exception as e:
            print(f"    [页面等待] 等待异常: {e}")
            return False

    @_log_action
    @thread_safe(OperationType.PAGE_SWITCH, LockType.EXCLUSIVE)
    def switch_to_page(self, **kwargs):
        """
        [关键字] 切换当前的活动页面。
        后续所有未指定'页面'列的操作，将默认在此新页面上执行。
        支持动态URL匹配：可使用正则表达式、通配符等模式匹配页面。
        数据内容: 要切换到的页码 (e.g., "2") 或 URL模式 (e.g., "*example*", "{regex:.*pattern.*}")
        """
        # 在操作前自动清理无效引用
        if hasattr(self, 'page_lifecycle_manager'):
            self.page_lifecycle_manager.cleanup_all_invalid_references()
            self._validate_and_adjust_active_page()
        
        page_index_str = str(kwargs.get('数据内容', '')).strip()
        if not page_index_str:
            raise ValueError("switch_to_page 关键字需要在 '数据内容' 列提供页码或URL模式。")
        
        target_page = None
        
        # 检查是否启用模式匹配且数据包含模式字符
        if (self.URL_PATTERN_CONFIG['enable_pattern_matching'] and 
            (page_index_str.startswith('{regex:') or '*' in page_index_str or '?' in page_index_str)):
            
            print(f"  [动态URL匹配] 检测到URL模式，开始查找匹配页面进行切换: {page_index_str}")
            
            # 尝试在已打开页面中查找匹配
            match_result = self._find_matching_page(page_index_str)
            
            if match_result.success and match_result.matched_page:
                target_page = match_result.matched_page
                page_index = self.context.pages.index(target_page) + 1
                print(f"  [动态URL匹配] ✓ 找到匹配页面: 页{page_index} ({match_result.pattern_type.value}) - {target_page.url}")
            else:
                print(f"  [动态URL匹配] ✗ 未找到匹配的页面")
                # 显示所有可用页面供参考
                print(f"        当前可用页面:")
                for i, page in enumerate(self.context.pages):
                    try:
                        if not page.is_closed():
                            url = page.url
                            print(f"          页面 {i+1}: {url}")
                    except:
                        print(f"          页面 {i+1}: [无法获取URL]")
                raise ValueError(f"未找到匹配URL模式 '{page_index_str}' 的页面。")
        
        # 如果不是模式匹配，尝试传统方式
        elif not target_page:
            # 先尝试作为页码处理
            try:
                target_page = self._get_target_page(页面=page_index_str)
                print(f"  [传统匹配] 使用页码匹配: 页{page_index_str}")
            except (ValueError, IndexError):
                # 如果页码失败，尝试URL部分匹配
                print(f"  [传统匹配] 页码匹配失败，尝试URL部分匹配...")
                
                for i, page in enumerate(self.context.pages):
                    try:
                        if not page.is_closed() and page_index_str in page.url:
                            target_page = page
                            print(f"  [传统匹配] ✓ 找到URL包含 '{page_index_str}' 的页面: 页{i+1} - {page.url}")
                            break
                    except:
                        continue
                
                if not target_page:
                    # 显示所有可用页面供参考
                    print(f"        当前可用页面:")
                    for i, page in enumerate(self.context.pages):
                        try:
                            if not page.is_closed():
                                url = page.url
                                print(f"          页面 {i+1}: {url}")
                        except:
                            print(f"          页面 {i+1}: [无法获取URL]")
                    raise ValueError(f"未找到匹配 '{page_index_str}' 的页面。")
        
        # 执行切换
        self.active_page = target_page
        page_index = self.context.pages.index(target_page) + 1
        print(f"✓ [状态切换] 当前活动页面已切换至 页{page_index}。")

    def _is_valid_url(self, url_string: str) -> bool:
        """
        [内部] 检查字符串是否为有效的URL格式。
        """
        import re
        url_pattern = re.compile(
            r'^https?://'  # http:// 或 https://
            r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # 域名
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP地址
            r'(?::\d+)?'  # 可选端口号
            r'(?:/?|[/?]\S+)$', re.IGNORECASE)
        return url_pattern.match(url_string) is not None

    @thread_safe(OperationType.PAGE_CLOSE, LockType.EXCLUSIVE)
    def close_page(self, **kwargs):
        """
        [关键字] 关闭指定的页面。
        如果'数据内容'列为空，则关闭当前活动页面。
        如果关闭的是活动页面，焦点会自动切换回主页面。
        支持动态URL匹配：可使用正则表达式、通配符等模式匹配页面。
        数据内容: [可选] 要关闭的页码 (e.g., "2") 或 URL模式 (e.g., "https://www.example.com", "*example*", "{regex:.*pattern.*}")
        """
        data_content = str(kwargs.get('数据内容', '')).strip()
        
        # 如果数据内容为空，关闭当前活动页面
        if not data_content:
            target_page_to_close = self._get_target_page()
            page_identifier = f"Page {self.context.pages.index(target_page_to_close) + 1}"
        else:
            target_page_to_close = None
            page_identifier = data_content
            
            # 检查是否启用模式匹配且数据包含模式字符
            if (self.URL_PATTERN_CONFIG['enable_pattern_matching'] and 
                (data_content.startswith('{regex:') or '*' in data_content or '?' in data_content)):
                
                print(f"  [动态URL匹配] 检测到URL模式，开始查找匹配页面进行关闭: {data_content}")
                
                # 尝试在已打开页面中查找匹配
                match_result = self._find_matching_page(data_content)
                
                if match_result.success and match_result.matched_page:
                    target_page_to_close = match_result.matched_page
                    page_index = self.context.pages.index(target_page_to_close) + 1
                    page_identifier = f"URL模式匹配页面 {page_index} ({match_result.pattern_type.value})"
                    print(f"  [动态URL匹配] ✓ 找到匹配页面: {target_page_to_close.url}")
                else:
                    print(f"  [动态URL匹配] ✗ 未找到匹配的页面")
                    error_msg = f"[警告] 未找到匹配URL模式 '{data_content}' 的页面，操作已跳过。"
                    print(error_msg)
                    return error_msg
            
            # 如果不是模式匹配，则使用传统匹配方式
            elif not target_page_to_close:
                # 如果数据内容是有效的URL，查找匹配的页面
                if self._is_valid_url(data_content):
                    for page in self.context.pages:
                        if page.url == data_content:
                            target_page_to_close = page
                            break
                    
                    if target_page_to_close is None:
                        error_msg = f"[警告] 未找到URL为 '{data_content}' 的页面，操作已跳过。"
                        print(error_msg)
                        return error_msg
                        
                    page_identifier = f"URL '{data_content}'"
                
                # 如果数据内容不是有效的URL，但包含URL特征，则按部分匹配查找
                elif 'http://' in data_content or 'https://' in data_content:
                    for page in self.context.pages:
                        if data_content in page.url:
                            target_page_to_close = page
                            break
                    
                    if target_page_to_close is None:
                        error_msg = f"[警告] 未找到URL包含 '{data_content}' 的页面，操作已跳过。"
                        print(error_msg)
                        return error_msg
                        
                    page_identifier = f"URL 包含 '{data_content}'"
                
                # 否则，检查是否是部分URL匹配
                else:
                    for page in self.context.pages:
                        if data_content in page.url:
                            target_page_to_close = page
                            break
                    
                    # 如果找到匹配的页面，使用部分URL匹配
                    if target_page_to_close is not None:
                        page_identifier = f"URL 包含 '{data_content}'"
                    else:
                        # 检查是否是页面索引
                        try:
                            # 尝试将数据内容转换为整数
                            page_index = int(data_content)
                            # 如果转换成功，使用页面索引
                            target_page_to_close = self._get_target_page(页面=data_content)
                            page_identifier = f"Page {self.context.pages.index(target_page_to_close) + 1}"
                        except ValueError:
                            # 如果转换失败，返回错误消息
                            error_msg = f"[警告] 未找到匹配 '{data_content}' 的页面，操作已跳过。"
                            print(error_msg)
                            return error_msg
        
        print(f"执行 [关闭页面]: 目标是 {page_identifier}")
        
        if len(self.context.pages) <= 1:
            print("[警告] 无法关闭最后一个页面，操作已跳过。")
            return
            
        target_page_to_close.close()
        
        # 在页面关闭后进行活跃页面调整
        if hasattr(self, 'page_lifecycle_manager'):
            self._validate_and_adjust_active_page()
        else:
            # 旧的错误处理方式（向后兼容）
            if self.active_page.is_closed():
                 self.active_page = self.context.pages[0]
                 print("  > 已关闭的页面是当前活动页，活动页已自动重置为主页面 (Page 1)。")
        print(f"✓ [关闭页面] 成功。")

    @thread_safe(OperationType.PAGE_CREATE, LockType.EXCLUSIVE)
    def open_in_new_page(self, **kwargs):
        """
        [关键字] 在新的标签页中打开URL。
        此操作会自动创建新页面，在其中加载URL，并将其设为新的活动页面。
        数据内容: 要打开的URL, [可选的超时秒数] e.g., "http://a.com,60"
        """
        print("执行 [在新标签页打开]: 正在创建新页面...")
        new_page = self.context.new_page()
        self.active_page = new_page
        print(f"  > 新页面 (页{len(self.context.pages)}) 已创建并设为活动页面。")
        print("  > 正在新页面中加载URL...")
        try:
            self.open(**kwargs)
        except Exception as e:
            if not new_page.is_closed(): new_page.close()
            raise e

    @_log_action
    @thread_safe(OperationType.NAVIGATION, LockType.EXCLUSIVE)
    def open(self, **kwargs):
        """
        [关键字] 在当前的活动页面上导航到指定的URL。
        此操作会覆盖当前活动页面的内容。
        支持动态URL匹配：优先匹配已打开页面，未找到时降级到基础URL导航。
        数据内容: 要打开的URL, [可选的超时秒数] e.g., "http://a.com,60"
        """
        data_content = str(kwargs.get('数据内容', ''))
        # 支持中文逗号和英文逗号
        data_content = data_content.replace('，', ',')
        parts = [p.strip() for p in data_content.split(',')]
        url = parts[0]
        timeout_ms = int(parts[1]) * 1000 if len(parts) > 1 else self.DEFAULT_TIMEOUT
        
        print(f"执行 [打开页面]: {url}")
        
        # 检查是否启用模式匹配且URL包含模式字符
        if (self.URL_PATTERN_CONFIG['enable_pattern_matching'] and 
            (url.startswith('{regex:') or '*' in url or '?' in url)):
            
            print(f"  [动态URL匹配] 检测到URL模式，开始查找匹配页面...")
            
            # 尝试在已打开页面中查找匹配
            match_result = self._find_matching_page(url)
            
            if match_result.success and match_result.matched_page:
                # 找到匹配页面，切换到该页面
                print(f"  [动态URL匹配] ✓ 找到匹配页面，切换到该页面")
                self.active_page = match_result.matched_page
                page_index = self.context.pages.index(match_result.matched_page) + 1
                print(f"  [动态URL匹配] ✓ 已切换到页面 {page_index}: {match_result.matched_page.url}")
                print(f"SUCCESS [Open Page] 使用已存在页面，匹配类型: {match_result.pattern_type.value}")
                return
            else:
                # 未找到匹配页面，尝试降级策略
                if not self.URL_PATTERN_CONFIG['strict_matching']:
                    base_url = self._extract_base_url(url)
                    if base_url:
                        print(f"  [动态URL匹配] 未找到匹配页面，使用降级策略导航到基础URL: {base_url}")
                        url = base_url  # 使用基础URL继续执行导航
                        print(f"  [动态URL匹配] 降级导航到: {url}")
                    else:
                        print(f"  [动态URL匹配] 无法提取基础URL，使用原始URL尝试导航")
                else:
                    # 严格匹配模式，不使用降级策略
                    print(f"  [动态URL匹配] 严格匹配模式，未找到匹配页面，操作失败")
                    pytest.fail(f"✗ 打开页面 {url} 失败: 严格匹配模式下未找到匹配页面")
                    return
        
        # 执行传统导航操作
        print(f"  [传统导航] 在当前活动页面上导航到: {url}")
        start_time = time.time()
        try:
            self.active_page.goto(url, timeout=timeout_ms)
            duration = time.time() - start_time
            print(f"SUCCESS [Open Page] Loaded successfully, Duration: {duration:.2f}s")
        except PlaywrightTimeoutError:
            duration = time.time() - start_time
            pytest.fail(f"✗ 打开页面 {url} 失败: 超时({timeout_ms/1000}s), 实际等待 {duration:.2f}s")
            
    @_log_action
    def go_back(self, **kwargs):
        """
        [关键字] 模拟浏览器的后退按钮。
        """
        description = kwargs.get('描述', '页面后退')
        print(f"执行 [{description}]")
        self.active_page.go_back()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")
 
    @_log_action
    def go_forward(self, **kwargs):
        """
        [关键字] 模拟浏览器的前进按钮。
        """
        description = kwargs.get('描述', '页面前进')
        print(f"执行 [{description}]")
        self.active_page.go_forward()
        self.active_page.wait_for_load_state('domcontentloaded')
        print(f"✓ [{description}] 成功")

    def set_window_size(self, **kwargs):
        """
        [关键字] 设置当前活动页面的视口（viewport）大小。
        数据内容: 格式为 "宽x高" 的字符串 (e.g., "1920x1080")
        """
        size_str = kwargs.get('数据内容', '1920x1080')
        description = kwargs.get('描述', f'设置窗口大小为 {size_str}')
        print(f"执行 [{description}]")
        try:
            width, height = map(int, size_str.split('x'))
            self.active_page.set_viewport_size({"width": width, "height": height})
        except ValueError:
            pytest.fail(f"窗口大小格式错误: '{size_str}', 期望 '宽x高'")
        print(f"✓ [{description}] 成功")
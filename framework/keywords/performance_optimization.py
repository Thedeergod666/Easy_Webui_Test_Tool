# -*- coding: utf-8 -*-
"""
URL匹配性能优化模块
提供缓存、索引和智能匹配算法优化
"""

import re
import time
import hashlib
from functools import lru_cache
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict, OrderedDict
from dataclasses import dataclass, field
from threading import RLock


@dataclass
class MatchCacheEntry:
    """匹配缓存条目"""
    pattern: str
    compiled_regex: Optional[re.Pattern] = None
    match_type: str = "unknown"
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    hit_count: int = 0
    
    def update_access(self):
        """更新访问信息"""
        self.access_count += 1
        self.last_access = time.time()
    
    def record_hit(self):
        """记录命中"""
        self.hit_count += 1
        self.update_access()


@dataclass
class URLIndexEntry:
    """URL索引条目"""
    url: str
    page_ref: Any  # 页面引用
    normalized_url: str = ""
    domain: str = ""
    path: str = ""
    created_at: float = field(default_factory=time.time)
    
    def __post_init__(self):
        """初始化后处理"""
        if not self.normalized_url:
            self.normalized_url = self.url.lower()
        
        if not self.domain or not self.path:
            self._parse_url()
    
    def _parse_url(self):
        """解析URL组件"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(self.url)
            self.domain = parsed.netloc.lower()
            self.path = parsed.path.lower()
        except Exception:
            self.domain = ""
            self.path = ""


class URLMatchingOptimizer:
    """URL匹配性能优化器"""
    
    def __init__(self, max_cache_size: int = 100, cache_ttl: int = 300):
        """
        初始化优化器
        
        Args:
            max_cache_size: 最大缓存大小
            cache_ttl: 缓存生存时间（秒）
        """
        self.max_cache_size = max_cache_size
        self.cache_ttl = cache_ttl
        
        # 编译缓存：模式 -> 编译后的正则表达式
        self.regex_cache: OrderedDict[str, MatchCacheEntry] = OrderedDict()
        
        # URL索引：快速精确匹配
        self.url_index: Dict[str, URLIndexEntry] = {}
        
        # 域名索引：按域名组织页面
        self.domain_index: Dict[str, List[URLIndexEntry]] = defaultdict(list)
        
        # 路径索引：按路径前缀组织页面
        self.path_index: Dict[str, List[URLIndexEntry]] = defaultdict(list)
        
        # 性能统计
        self.performance_stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'exact_matches': 0,
            'pattern_matches': 0,
            'index_lookups': 0,
            'total_searches': 0,
            'average_search_time': 0.0
        }
        
        # 线程安全锁
        self._lock = RLock()
        
        print(f"    [性能优化] URL匹配优化器已初始化 (缓存大小: {max_cache_size}, TTL: {cache_ttl}s)")
    
    def add_page_to_index(self, url: str, page_ref: Any) -> None:
        """
        将页面添加到索引
        
        Args:
            url: 页面URL
            page_ref: 页面引用
        """
        with self._lock:
            try:
                # 创建索引条目
                index_entry = URLIndexEntry(url=url, page_ref=page_ref)
                
                # 添加到URL索引
                normalized_url = url.lower()
                self.url_index[normalized_url] = index_entry
                
                # 添加到域名索引
                if index_entry.domain:
                    self.domain_index[index_entry.domain].append(index_entry)
                
                # 添加到路径索引
                if index_entry.path:
                    # 为路径的各个前缀建立索引
                    path_parts = index_entry.path.strip('/').split('/')
                    for i in range(len(path_parts)):
                        prefix = '/' + '/'.join(path_parts[:i+1])
                        self.path_index[prefix].append(index_entry)
                
                print(f"    [性能优化] 页面已添加到索引: {url}")
                
            except Exception as e:
                print(f"    [性能优化] 添加页面索引失败: {e}")
    
    def remove_page_from_index(self, url: str) -> bool:
        """
        从索引中移除页面
        
        Args:
            url: 页面URL
            
        Returns:
            bool: 是否成功移除
        """
        with self._lock:
            try:
                normalized_url = url.lower()
                
                # 从URL索引中移除
                if normalized_url in self.url_index:
                    index_entry = self.url_index.pop(normalized_url)
                    
                    # 从域名索引中移除
                    if index_entry.domain in self.domain_index:
                        self.domain_index[index_entry.domain] = [
                            entry for entry in self.domain_index[index_entry.domain]
                            if entry.url != url
                        ]
                        
                        # 如果域名下没有页面了，删除域名索引
                        if not self.domain_index[index_entry.domain]:
                            del self.domain_index[index_entry.domain]
                    
                    # 从路径索引中移除
                    if index_entry.path:
                        path_parts = index_entry.path.strip('/').split('/')
                        for i in range(len(path_parts)):
                            prefix = '/' + '/'.join(path_parts[:i+1])
                            if prefix in self.path_index:
                                self.path_index[prefix] = [
                                    entry for entry in self.path_index[prefix]
                                    if entry.url != url
                                ]
                                
                                # 如果路径下没有页面了，删除路径索引
                                if not self.path_index[prefix]:
                                    del self.path_index[prefix]
                    
                    print(f"    [性能优化] 页面已从索引移除: {url}")
                    return True
                
                return False
                
            except Exception as e:
                print(f"    [性能优化] 移除页面索引失败: {e}")
                return False
    
    @lru_cache(maxsize=128)
    def _get_pattern_hash(self, pattern: str) -> str:
        """获取模式的哈希值（用于缓存键）"""
        return hashlib.md5(pattern.encode('utf-8')).hexdigest()[:16]
    
    def get_compiled_regex(self, pattern: str, pattern_type: str = "regex") -> Optional[re.Pattern]:
        """
        获取编译后的正则表达式（带缓存）
        
        Args:
            pattern: 正则表达式模式
            pattern_type: 模式类型 (regex, wildcard)
            
        Returns:
            Optional[re.Pattern]: 编译后的正则表达式
        """
        with self._lock:
            pattern_hash = self._get_pattern_hash(pattern)
            
            # 检查缓存
            if pattern_hash in self.regex_cache:
                cache_entry = self.regex_cache[pattern_hash]
                
                # 检查是否过期
                if time.time() - cache_entry.created_at < self.cache_ttl:
                    cache_entry.record_hit()
                    self.performance_stats['cache_hits'] += 1
                    
                    # LRU更新：移动到末尾
                    self.regex_cache.move_to_end(pattern_hash)
                    return cache_entry.compiled_regex
                else:
                    # 缓存过期，删除
                    del self.regex_cache[pattern_hash]
            
            # 缓存未命中，编译新的正则表达式
            self.performance_stats['cache_misses'] += 1
            
            try:
                if pattern_type == "wildcard":
                    # 将通配符转换为正则表达式
                    escaped_pattern = re.escape(pattern)
                    escaped_pattern = escaped_pattern.replace('\\*', '.*')
                    escaped_pattern = escaped_pattern.replace('\\?', '.')
                    compiled_regex = re.compile(f'^{escaped_pattern}$', re.IGNORECASE)
                else:
                    # 直接编译正则表达式
                    compiled_regex = re.compile(pattern, re.IGNORECASE)
                
                # 添加到缓存
                cache_entry = MatchCacheEntry(
                    pattern=pattern,
                    compiled_regex=compiled_regex,
                    match_type=pattern_type
                )
                
                self.regex_cache[pattern_hash] = cache_entry
                
                # 缓存大小控制：LRU淘汰
                while len(self.regex_cache) > self.max_cache_size:
                    self.regex_cache.popitem(last=False)  # 删除最旧的
                
                print(f"    [性能优化] 正则表达式已编译并缓存: {pattern[:50]}...")
                return compiled_regex
                
            except re.error as e:
                print(f"    [性能优化] 正则表达式编译失败: {pattern}, 错误: {e}")
                return None
    
    def fast_exact_match(self, target_url: str) -> Optional[Any]:
        """
        快速精确匹配
        
        Args:
            target_url: 目标URL
            
        Returns:
            Optional[Any]: 匹配的页面引用
        """
        with self._lock:
            self.performance_stats['index_lookups'] += 1
            
            normalized_url = target_url.lower()
            if normalized_url in self.url_index:
                self.performance_stats['exact_matches'] += 1
                return self.url_index[normalized_url].page_ref
            
            return None
    
    def optimized_pattern_match(self, pattern: str, target_url: str, 
                              pattern_type: str = "regex") -> Tuple[bool, float]:
        """
        优化的模式匹配
        
        Args:
            pattern: 匹配模式
            target_url: 目标URL
            pattern_type: 模式类型
            
        Returns:
            Tuple[bool, float]: (是否匹配, 匹配评分)
        """
        start_time = time.time()
        
        try:
            # 获取编译后的正则表达式（带缓存）
            compiled_regex = self.get_compiled_regex(pattern, pattern_type)
            
            if compiled_regex is None:
                return False, 0.0
            
            # 执行匹配
            match = compiled_regex.search(target_url.lower())
            
            if match:
                # 计算匹配评分
                match_length = len(match.group(0))
                total_length = len(target_url)
                score = min(1.0, match_length / total_length * 1.2)
                
                self.performance_stats['pattern_matches'] += 1
                return True, score
            
            return False, 0.0
            
        except Exception as e:
            print(f"    [性能优化] 模式匹配失败: {e}")
            return False, 0.0
        
        finally:
            # 更新性能统计
            match_time = time.time() - start_time
            self.performance_stats['total_searches'] += 1
            
            # 更新平均搜索时间
            total_time = (self.performance_stats['average_search_time'] * 
                         (self.performance_stats['total_searches'] - 1) + match_time)
            self.performance_stats['average_search_time'] = total_time / self.performance_stats['total_searches']
    
    def cleanup_expired_cache(self) -> int:
        """
        清理过期缓存
        
        Returns:
            int: 清理的条目数量
        """
        with self._lock:
            current_time = time.time()
            expired_keys = []
            
            for key, entry in self.regex_cache.items():
                if current_time - entry.created_at > self.cache_ttl:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.regex_cache[key]
            
            if expired_keys:
                print(f"    [性能优化] 已清理 {len(expired_keys)} 个过期缓存条目")
            
            return len(expired_keys)
    
    def fast_domain_search(self, url: str) -> list:
        """
        通过域名快速搜索相关页面
        
        Args:
            url: 目标URL
            
        Returns:
            list: 匹配的页面引用列表
        """
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            with self._lock:
                if domain in self.domain_index:
                    return list(self.domain_index[domain])
                return []
        except Exception as e:
            print(f"    [性能优化] 域名搜索失败: {e}")
            return []
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        获取性能报告
        
        Returns:
            Dict[str, Any]: 性能统计信息
        """
        with self._lock:
            # 计算缓存命中率
            total_requests = self.performance_stats['cache_hits'] + self.performance_stats['cache_misses']
            cache_hit_rate = (self.performance_stats['cache_hits'] / total_requests 
                            if total_requests > 0 else 0)
            
            return {
                'cache_statistics': {
                    'cache_size': len(self.regex_cache),
                    'max_cache_size': self.max_cache_size,
                    'cache_hit_rate': cache_hit_rate,
                    'cache_hits': self.performance_stats['cache_hits'],
                    'cache_misses': self.performance_stats['cache_misses']
                },
                'index_statistics': {
                    'total_indexed_urls': len(self.url_index),
                    'domain_count': len(self.domain_index),
                    'path_prefixes': len(self.path_index),
                    'index_lookups': self.performance_stats['index_lookups']
                },
                'matching_statistics': {
                    'exact_matches': self.performance_stats['exact_matches'],
                    'pattern_matches': self.performance_stats['pattern_matches'],
                    'total_searches': self.performance_stats['total_searches'],
                    'average_search_time_ms': self.performance_stats['average_search_time'] * 1000
                }
            }
    
    def optimize_indexes(self) -> None:
        """
        优化索引结构
        """
        with self._lock:
            print(f"    [性能优化] 开始索引优化...")
            
            # 清理空的索引条目
            empty_domains = [domain for domain, entries in self.domain_index.items() if not entries]
            for domain in empty_domains:
                del self.domain_index[domain]
            
            empty_paths = [path for path, entries in self.path_index.items() if not entries]
            for path in empty_paths:
                del self.path_index[path]
            
            # 清理过期缓存
            expired_count = self.cleanup_expired_cache()
            
            print(f"    [性能优化] 索引优化完成, 清理了 {len(empty_domains)} 个空域名, "
                  f"{len(empty_paths)} 个空路径, {expired_count} 个过期缓存")
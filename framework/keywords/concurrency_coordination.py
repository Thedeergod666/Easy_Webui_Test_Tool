# -*- coding: utf-8 -*-
"""
并发协调模块
提供多页面环境下的并发操作协调机制
"""

import time
import threading
import queue
from enum import Enum
from typing import Dict, Any, Optional, Callable, Union
from dataclasses import dataclass, field
from functools import wraps
import contextlib


class OperationType(Enum):
    """操作类型枚举"""
    PAGE_SWITCH = "page_switch"         # 页面切换
    PAGE_CREATE = "page_create"         # 页面创建
    PAGE_CLOSE = "page_close"           # 页面关闭
    STATE_QUERY = "state_query"         # 状态查询
    ELEMENT_OPERATION = "element_op"    # 元素操作
    NAVIGATION = "navigation"           # 页面导航
    CLEANUP = "cleanup"                 # 清理操作


class LockType(Enum):
    """锁类型枚举"""
    EXCLUSIVE = "exclusive"     # 排他锁
    SHARED = "shared"          # 共享锁
    UPGRADE = "upgrade"        # 可升级锁


@dataclass
class OperationRequest:
    """操作请求数据结构"""
    operation_id: str
    operation_type: OperationType
    lock_type: LockType
    timeout: float = 10.0
    priority: int = 0  # 优先级，数值越低优先级越高
    created_at: float = field(default_factory=time.time)
    callback: Optional[Callable] = None
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)
    
    def __lt__(self, other):
        """支持优先级队列排序"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class ConcurrencyCoordinator:
    """并发协调器"""
    
    def __init__(self):
        """初始化并发协调器"""
        # 核心锁机制
        self._page_switch_lock = threading.RLock()      # 页面切换锁
        self._page_create_lock = threading.RLock()      # 页面创建锁
        self._state_validation_lock = threading.RLock() # 状态验证锁
        self._cleanup_lock = threading.RLock()          # 清理操作锁
        
        # 读写锁实现（用于状态查询）
        self._readers_count = 0
        self._readers_lock = threading.Lock()
        self._writers_lock = threading.Lock()
        
        # 操作队列系统
        self._operation_queue = queue.PriorityQueue()
        self._active_operations: Dict[str, OperationRequest] = {}
        self._operation_history: list = []
        
        # 性能统计
        self.stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'timeout_operations': 0,
            'concurrent_conflicts': 0,
            'average_wait_time': 0.0,
            'lock_contention_count': 0
        }
        
        # 配置参数
        self.max_queue_size = 100
        self.max_history_size = 200
        self.default_timeout = 10.0
        
        print(f"    [并发协调] 并发协调器已初始化")
    
    def _get_operation_lock(self, operation_type: OperationType) -> threading.RLock:
        """根据操作类型获取相应的锁"""
        lock_mapping = {
            OperationType.PAGE_SWITCH: self._page_switch_lock,
            OperationType.PAGE_CREATE: self._page_create_lock,
            OperationType.PAGE_CLOSE: self._page_switch_lock,  # 页面关闭也需要切换锁
            OperationType.STATE_QUERY: self._state_validation_lock,
            OperationType.ELEMENT_OPERATION: self._state_validation_lock,
            OperationType.NAVIGATION: self._page_switch_lock,
            OperationType.CLEANUP: self._cleanup_lock
        }
        return lock_mapping.get(operation_type, self._state_validation_lock)
    
    @contextlib.contextmanager
    def _acquire_shared_lock(self, timeout: float = 10.0):
        """获取共享锁（读锁）"""
        acquired = False
        start_time = time.time()
        
        try:
            # 获取读者计数锁
            if self._readers_lock.acquire(timeout=timeout):
                try:
                    self._readers_count += 1
                    if self._readers_count == 1:
                        # 第一个读者需要获取写锁
                        remaining_timeout = timeout - (time.time() - start_time)
                        if remaining_timeout <= 0 or not self._writers_lock.acquire(timeout=remaining_timeout):
                            self._readers_count -= 1
                            raise TimeoutError("获取共享锁超时")
                    acquired = True
                    print(f"    [并发协调] 共享锁已获取，当前读者数: {self._readers_count}")
                finally:
                    self._readers_lock.release()
            else:
                raise TimeoutError("获取读者计数锁超时")
            
            yield
            
        finally:
            if acquired:
                with self._readers_lock:
                    self._readers_count -= 1
                    if self._readers_count == 0:
                        # 最后一个读者释放写锁
                        self._writers_lock.release()
                    print(f"    [并发协调] 共享锁已释放，剩余读者数: {self._readers_count}")
    
    @contextlib.contextmanager
    def _acquire_exclusive_lock(self, lock: threading.RLock, timeout: float = 10.0):
        """获取排他锁"""
        acquired = False
        start_time = time.time()
        
        try:
            if lock.acquire(timeout=timeout):
                acquired = True
                print(f"    [并发协调] 排他锁已获取: {lock}")
                yield
            else:
                raise TimeoutError("获取排他锁超时")
        finally:
            if acquired:
                lock.release()
                print(f"    [并发协调] 排他锁已释放: {lock}")
    
    def coordinate_operation(self, operation_type: OperationType, 
                           operation_func: Callable, 
                           lock_type: LockType = LockType.EXCLUSIVE,
                           timeout: float = None,
                           priority: int = 0,
                           **kwargs) -> Any:
        """
        协调单个操作的执行
        
        Args:
            operation_type: 操作类型
            operation_func: 要执行的操作函数
            lock_type: 锁类型
            timeout: 超时时间
            priority: 优先级 (数值越小优先级越高)
            **kwargs: 传递给操作函数的参数
            
        Returns:
            Any: 操作执行结果
        """
        if timeout is None:
            timeout = self.default_timeout
        
        operation_id = f"{operation_type.value}_{int(time.time() * 1000000)}"
        start_time = time.time()
        
        # 创建操作请求
        request = OperationRequest(
            operation_id=operation_id,
            operation_type=operation_type,
            lock_type=lock_type,
            timeout=timeout,
            priority=priority,
            callback=operation_func,
            kwargs=kwargs
        )
        
        print(f"    [并发协调] 开始协调操作: {operation_id} ({operation_type.value}), 优先级: {priority}")
        
        try:
            self.stats['total_operations'] += 1
            
            # 记录活动操作
            self._active_operations[operation_id] = request
            
            # 使用优先级队列执行操作
            result = self._execute_with_priority(request)
            
            # 记录成功统计
            self.stats['successful_operations'] += 1
            execution_time = time.time() - start_time
            self._update_average_wait_time(execution_time)
            
            print(f"    [并发协调] 操作完成: {operation_id}, 耗时: {execution_time:.3f}s")
            return result
            
        except TimeoutError as e:
            self.stats['timeout_operations'] += 1
            print(f"    [并发协调] 操作超时: {operation_id}, {e}")
            raise
            
        except Exception as e:
            self.stats['failed_operations'] += 1
            print(f"    [并发协调] 操作失败: {operation_id}, {e}")
            raise
            
        finally:
            # 清理活动操作记录
            if operation_id in self._active_operations:
                del self._active_operations[operation_id]
            
            # 记录操作历史
            self._record_operation_history(request, time.time() - start_time)
    
    def _execute_with_priority(self, request: OperationRequest) -> Any:
        """使用优先级队列执行操作"""
        # 将操作放入优先级队列
        operation_event = threading.Event()
        result_holder = {'result': None, 'exception': None}
        
        # 包装操作函数以捕获结果
        def wrapper():
            try:
                result_holder['result'] = self._execute_coordinated_operation(request)
            except Exception as e:
                result_holder['exception'] = e
            finally:
                operation_event.set()
        
        # 创建包装后的请求
        wrapped_request = OperationRequest(
            operation_id=request.operation_id,
            operation_type=request.operation_type,
            lock_type=request.lock_type,
            timeout=request.timeout,
            priority=request.priority,
            callback=wrapper,
            kwargs={}
        )
        
        # 检查是否有高优先级操作等待
        if self._has_higher_priority_operations(request.priority):
            # 等待一小段时间让高优先级操作先执行
            time.sleep(0.001 * (request.priority + 1))
        
        # 直接执行操作
        wrapper()
        
        # 等待操作完成
        if not operation_event.wait(timeout=request.timeout):
            raise TimeoutError(f"操作超时: {request.operation_id}")
        
        # 检查是否有异常
        if result_holder['exception']:
            raise result_holder['exception']
        
        return result_holder['result']
    
    def _has_higher_priority_operations(self, current_priority: int) -> bool:
        """检查是否有更高优先级的操作在等待"""
        for op in self._active_operations.values():
            if op.priority < current_priority:
                return True
        return False
    
    def _execute_coordinated_operation(self, request: OperationRequest) -> Any:
        """执行协调后的操作"""
        if request.lock_type == LockType.SHARED:
            # 共享锁执行
            with self._acquire_shared_lock(request.timeout):
                return request.callback(**request.kwargs)
        
        elif request.lock_type == LockType.EXCLUSIVE:
            # 排他锁执行
            operation_lock = self._get_operation_lock(request.operation_type)
            with self._acquire_exclusive_lock(operation_lock, request.timeout):
                return request.callback(**request.kwargs)
        
        else:
            # 默认无锁执行
            return request.callback(**request.kwargs)
    
    def _update_average_wait_time(self, execution_time: float):
        """更新平均等待时间统计"""
        current_avg = self.stats['average_wait_time']
        total_ops = self.stats['successful_operations']
        
        if total_ops == 1:
            self.stats['average_wait_time'] = execution_time
        else:
            # 滑动平均
            self.stats['average_wait_time'] = (current_avg * (total_ops - 1) + execution_time) / total_ops
    
    def _record_operation_history(self, request: OperationRequest, execution_time: float):
        """记录操作历史"""
        history_entry = {
            'operation_id': request.operation_id,
            'operation_type': request.operation_type.value,
            'lock_type': request.lock_type.value,
            'priority': request.priority,
            'execution_time': execution_time,
            'timestamp': time.time(),
            'success': True  # 这里简化处理，实际应该根据执行结果设置
        }
        
        self._operation_history.append(history_entry)
        
        # 限制历史记录大小
        if len(self._operation_history) > self.max_history_size:
            self._operation_history = self._operation_history[-self.max_history_size//2:]
    
    def detect_deadlock(self) -> list:
        """死锁检测（简化实现）"""
        deadlock_operations = []
        current_time = time.time()
        
        # 检查长时间等待的操作
        for operation_id, request in self._active_operations.items():
            wait_time = current_time - request.created_at
            if wait_time > request.timeout * 2:  # 超过2倍超时时间
                deadlock_operations.append({
                    'operation_id': operation_id,
                    'operation_type': request.operation_type.value,
                    'wait_time': wait_time,
                    'timeout': request.timeout
                })
        
        if deadlock_operations:
            print(f"    [并发协调] 检测到可能的死锁操作: {len(deadlock_operations)}个")
        
        return deadlock_operations
    
    def get_concurrency_stats(self) -> Dict[str, Any]:
        """获取并发统计信息"""
        return {
            'performance_stats': {
                'total_operations': self.stats['total_operations'],
                'successful_operations': self.stats['successful_operations'],
                'failed_operations': self.stats['failed_operations'],
                'timeout_operations': self.stats['timeout_operations'],
                'success_rate': (self.stats['successful_operations'] / max(1, self.stats['total_operations'])),
                'average_wait_time': self.stats['average_wait_time']
            },
            'concurrency_stats': {
                'active_operations_count': len(self._active_operations),
                'concurrent_conflicts': self.stats['concurrent_conflicts'],
                'lock_contention_count': self.stats['lock_contention_count'],
                'queue_size': self._operation_queue.qsize()
            },
            'system_health': {
                'potential_deadlocks': len(self.detect_deadlock()),
                'history_size': len(self._operation_history),
                'memory_usage_mb': len(self._operation_history) * 0.001  # 简化估算
            }
        }
    
    def cleanup_expired_operations(self) -> int:
        """清理过期操作"""
        current_time = time.time()
        expired_operations = []
        
        for operation_id, request in list(self._active_operations.items()):
            if current_time - request.created_at > request.timeout * 3:
                expired_operations.append(operation_id)
        
        for operation_id in expired_operations:
            del self._active_operations[operation_id]
            print(f"    [并发协调] 清理过期操作: {operation_id}")
        
        return len(expired_operations)


class ConcurrencyCoordinationMixin:
    """并发协调Mixin类"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.concurrency_coordinator = ConcurrencyCoordinator()
    
    def safe_coordinate(self, operation_type: OperationType, 
                       operation_func: Callable,
                       lock_type: LockType = LockType.EXCLUSIVE,
                       timeout: float = None,
                       priority: int = 0,
                       **kwargs) -> Any:
        """
        安全协调操作的执行
        
        Args:
            operation_type: 操作类型
            operation_func: 要执行的操作函数
            lock_type: 锁类型
            timeout: 超时时间
            priority: 优先级
            **kwargs: 传递给操作函数的参数
            
        Returns:
            Any: 操作执行结果
        """
        return self.concurrency_coordinator.coordinate_operation(
            operation_type=operation_type,
            operation_func=operation_func,
            lock_type=lock_type,
            timeout=timeout,
            priority=priority,
            **kwargs
        )
    
    def coordinate_page_switch(self, switch_func: Callable, **kwargs) -> Any:
        """协调页面切换操作"""
        return self.safe_coordinate(
            operation_type=OperationType.PAGE_SWITCH,
            operation_func=switch_func,
            lock_type=LockType.EXCLUSIVE,
            timeout=5.0,
            priority=1,  # 高优先级
            **kwargs
        )
    
    def coordinate_page_creation(self, create_func: Callable, **kwargs) -> Any:
        """协调页面创建操作"""
        return self.safe_coordinate(
            operation_type=OperationType.PAGE_CREATE,
            operation_func=create_func,
            lock_type=LockType.EXCLUSIVE,
            timeout=10.0,
            priority=2,
            **kwargs
        )
    
    def coordinate_state_query(self, query_func: Callable, **kwargs) -> Any:
        """协调状态查询操作"""
        return self.safe_coordinate(
            operation_type=OperationType.STATE_QUERY,
            operation_func=query_func,
            lock_type=LockType.SHARED,
            timeout=3.0,
            priority=5,  # 较低优先级
            **kwargs
        )
    
    def coordinate_cleanup(self, cleanup_func: Callable, **kwargs) -> Any:
        """协调清理操作"""
        return self.safe_coordinate(
            operation_type=OperationType.CLEANUP,
            operation_func=cleanup_func,
            lock_type=LockType.EXCLUSIVE,
            timeout=15.0,
            priority=0,  # 最高优先级
            **kwargs
        )
    
    def get_coordination_stats(self):
        """
        [关键字] 获取并发协调统计信息
        用于监控和调试并发操作性能
        """
        stats = self.concurrency_coordinator.get_concurrency_stats()
        print(f"执行 [并发统计]: 当前并发协调统计")
        
        # 性能统计
        perf_stats = stats['performance_stats']
        print(f"  > 性能指标:")
        print(f"    总操作数: {perf_stats['total_operations']}")
        print(f"    成功操作数: {perf_stats['successful_operations']}")
        print(f"    失败操作数: {perf_stats['failed_operations']}")
        print(f"    超时操作数: {perf_stats['timeout_operations']}")
        print(f"    成功率: {perf_stats['success_rate']:.2%}")
        print(f"    平均等待时间: {perf_stats['average_wait_time']:.3f}s")
        
        # 并发统计
        conc_stats = stats['concurrency_stats']
        print(f"  > 并发状态:")
        print(f"    活动操作数: {conc_stats['active_operations_count']}")
        print(f"    并发冲突数: {conc_stats['concurrent_conflicts']}")
        print(f"    锁竞争次数: {conc_stats['lock_contention_count']}")
        print(f"    队列大小: {conc_stats['queue_size']}")
        
        # 系统健康
        health_stats = stats['system_health']
        print(f"  > 系统健康:")
        print(f"    潜在死锁数: {health_stats['potential_deadlocks']}")
        print(f"    历史记录数: {health_stats['history_size']}")
        print(f"    内存使用: {health_stats['memory_usage_mb']:.2f}MB")
        
        return stats
    
    def cleanup_coordination(self):
        """
        [关键字] 清理并发协调状态
        清理过期操作和历史记录
        """
        print(f"执行 [并发清理]: 开始清理协调状态...")
        
        # 清理过期操作
        expired_count = self.concurrency_coordinator.cleanup_expired_operations()
        
        # 检测死锁
        deadlocks = self.concurrency_coordinator.detect_deadlock()
        
        print(f"  > 清理结果:")
        print(f"    清理过期操作: {expired_count}个")
        print(f"    检测到死锁: {len(deadlocks)}个")
        
        if deadlocks:
            print(f"    死锁详情:")
            for deadlock in deadlocks:
                print(f"      操作ID: {deadlock['operation_id']}")
                print(f"      类型: {deadlock['operation_type']}")
                print(f"      等待时间: {deadlock['wait_time']:.2f}s")
        
        print(f"✓ [并发清理] 完成")


def thread_safe(operation_type: OperationType, lock_type: LockType = LockType.EXCLUSIVE):
    """线程安全装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 检查是否有并发协调器
            if hasattr(self, 'concurrency_coordinator'):
                return self.concurrency_coordinator.coordinate_operation(
                    operation_type=operation_type,
                    operation_func=lambda: func(self, *args, **kwargs),
                    lock_type=lock_type
                )
            else:
                # 回退到原始函数执行
                return func(self, *args, **kwargs)
        return wrapper
    return decorator
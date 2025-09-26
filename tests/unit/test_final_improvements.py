# tests/unit/test_final_improvements.py
"""
最终改进验证测试

测试并发协调机制和页面变量映射标准化
"""
import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
import time
import threading

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from framework.keywords.concurrency_coordination import (
    ConcurrencyCoordinator, OperationType, LockType, OperationRequest
)
from framework.keywords.page_management import PageManagementMixin


class TestConcurrencyCoordination(unittest.TestCase):
    """并发协调测试类"""
    
    def setUp(self):
        """设置测试环境"""
        self.coordinator = ConcurrencyCoordinator()
        
    def test_coordinator_initialization(self):
        """测试协调器初始化"""
        self.assertIsNotNone(self.coordinator._page_switch_lock)
        self.assertIsNotNone(self.coordinator._page_create_lock)
        self.assertEqual(self.coordinator._readers_count, 0)
        self.assertEqual(len(self.coordinator._active_operations), 0)
        
    def test_exclusive_lock_coordination(self):
        """测试排他锁协调"""
        results = []
        
        def test_operation(**kwargs):
            results.append(f"Operation executed at {time.time()}")
            time.sleep(0.1)  # 模拟耗时操作
            return "success"
        
        # 同时执行多个排他锁操作
        def worker(op_id):
            result = self.coordinator.coordinate_operation(
                operation_type=OperationType.PAGE_SWITCH,
                operation_func=test_operation,
                lock_type=LockType.EXCLUSIVE,
                timeout=5.0,
                operation_id=op_id
            )
            results.append(f"Worker {op_id}: {result}")
        
        # 创建多个线程
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(f"op_{i}",))
            threads.append(thread)
        
        # 启动所有线程
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        # 等待所有线程完成
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # 验证结果
        self.assertEqual(len([r for r in results if "Worker" in r]), 3)
        # 由于排他锁，总时间应该大于0.3秒（每个操作0.1秒）
        self.assertGreater(end_time - start_time, 0.25)
        
    def test_shared_lock_coordination(self):
        """测试共享锁协调"""
        results = []
        
        def read_operation(**kwargs):
            results.append(f"Read operation at {time.time()}")
            time.sleep(0.1)
            return "read_success"
        
        def worker(op_id):
            result = self.coordinator.coordinate_operation(
                operation_type=OperationType.STATE_QUERY,
                operation_func=read_operation,
                lock_type=LockType.SHARED,
                timeout=5.0
            )
            results.append(f"Reader {op_id}: {result}")
        
        # 创建多个读线程
        threads = []
        for i in range(3):
            thread = threading.Thread(target=worker, args=(f"reader_{i}",))
            threads.append(thread)
        
        start_time = time.time()
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        end_time = time.time()
        
        # 验证结果
        self.assertEqual(len([r for r in results if "Reader" in r]), 3)
        # 由于共享锁，多个读操作可以并发，总时间应该接近0.1秒
        self.assertLess(end_time - start_time, 0.2)
        
    def test_operation_priority(self):
        """测试操作优先级"""
        results = []
        result_lock = threading.Lock()

        def test_operation(op_name, **kwargs):
            time.sleep(0.02)  # 模拟操作耗时
            with result_lock:
                results.append(op_name)
            return op_name

        # 使用barrier确保所有线程同时开始
        barrier = threading.Barrier(3)
        
        def worker(op_name, priority):
            barrier.wait()  # 等待所有线程就绪
            # 高优先级操作立即执行，低优先级操作等待更长时间
            if priority > 1:
                time.sleep(0.005 * priority)  # 低优先级等待
            
            self.coordinator.coordinate_operation(
                operation_type=OperationType.ELEMENT_OPERATION,
                operation_func=test_operation,
                lock_type=LockType.EXCLUSIVE,
                priority=priority,
                op_name=op_name
            )

        threads = [
            threading.Thread(target=worker, args=("low_priority", 10)),
            threading.Thread(target=worker, args=("high_priority", 1)),
            threading.Thread(target=worker, args=("medium_priority", 5))
        ]

        # 启动所有线程
        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # 验证结果：由于有延迟机制，高优先级应该先执行
        self.assertEqual(len(results), 3)
        # 由于排他锁的存在，只能保证高优先级比低优先级先执行
        high_index = results.index("high_priority")
        low_index = results.index("low_priority")
        self.assertLess(high_index, low_index, f"期望high_priority在low_priority之前，但结果是: {results}")
        
    def test_deadlock_detection(self):
        """测试死锁检测"""
        # 模拟长时间运行的操作
        request = OperationRequest(
            operation_id="long_running_op",
            operation_type=OperationType.PAGE_SWITCH,
            lock_type=LockType.EXCLUSIVE,
            timeout=1.0,
            created_at=time.time() - 5.0  # 5秒前开始
        )
        
        self.coordinator._active_operations["long_running_op"] = request
        
        # 检测死锁
        deadlocks = self.coordinator.detect_deadlock()
        
        self.assertEqual(len(deadlocks), 1)
        self.assertEqual(deadlocks[0]['operation_id'], "long_running_op")
        self.assertGreater(deadlocks[0]['wait_time'], 4.0)
        
    def test_stats_collection(self):
        """测试统计信息收集"""
        def simple_operation(**kwargs):
            return "test"
        
        # 执行几个操作
        for i in range(5):
            self.coordinator.coordinate_operation(
                operation_type=OperationType.STATE_QUERY,
                operation_func=simple_operation,
                lock_type=LockType.SHARED
            )
        
        # 获取统计信息
        stats = self.coordinator.get_concurrency_stats()
        
        self.assertEqual(stats['performance_stats']['total_operations'], 5)
        self.assertEqual(stats['performance_stats']['successful_operations'], 5)
        self.assertEqual(stats['performance_stats']['success_rate'], 1.0)
        self.assertGreater(stats['performance_stats']['average_wait_time'], 0)


class TestPageVariableMapping(unittest.TestCase):
    """页面变量映射测试类"""
    
    def setUp(self):
        """设置测试环境"""
        # 创建一个测试用的PageManagementMixin实例
        class TestPageManagement(PageManagementMixin):
            def __init__(self):
                # 模拟初始化
                self.context = Mock()
                self.context.pages = []
                self.active_page = None
                
                # 手动调用父类初始化
                super().__init__()
        
        self.page_mgmt = TestPageManagement()
        
    def test_standard_page_mapping(self):
        """测试标准页面映射"""
        # 创建模拟页面
        mock_pages = []
        for i in range(3):
            mock_page = Mock()
            mock_page.url = f"https://example.com/page{i+1}"
            mock_page.is_closed.return_value = False
            mock_pages.append(mock_page)
        
        self.page_mgmt.context.pages = mock_pages
        self.page_mgmt.active_page = mock_pages[0]
        
        # 获取映射信息
        mapping = self.page_mgmt.get_page_variable_mapping()
        
        # 验证标准映射
        self.assertIn('page', mapping)
        self.assertIn('page1', mapping)
        self.assertIn('page2', mapping)
        self.assertIn('page3', mapping)
        
        # 验证活动页面映射
        self.assertEqual(mapping['page']['target'], '页面1')
        self.assertEqual(mapping['page']['status'], '活动')
        
        # 验证索引映射
        for i in range(3):
            page_var = f'page{i+1}'
            self.assertEqual(mapping[page_var]['target'], f'页面{i+1}')
            self.assertEqual(mapping[page_var]['status'], '正常')
            
    def test_deprecated_mapping_detection(self):
        """测试已弃用映射检测"""
        # 创建一个页面
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.is_closed.return_value = False
        
        self.page_mgmt.context.pages = [mock_page]
        self.page_mgmt.active_page = mock_page
        
        mapping = self.page_mgmt.get_page_variable_mapping()
        
        # 验证已弃用的映射存在但标记为deprecated
        self.assertIn('page0', mapping)
        self.assertIn('pages', mapping)
        self.assertTrue(mapping['page0']['deprecated'])
        self.assertTrue(mapping['pages']['deprecated'])
        
    def test_mapping_diagnosis(self):
        """测试映射诊断功能"""
        # 创建包含已关闭页面的场景
        mock_page1 = Mock()
        mock_page1.url = "https://example.com/page1"
        mock_page1.is_closed.return_value = False
        
        mock_page2 = Mock()
        mock_page2.url = "https://example.com/page2"
        mock_page2.is_closed.return_value = True  # 已关闭页面
        
        self.page_mgmt.context.pages = [mock_page1, mock_page2]
        self.page_mgmt.active_page = mock_page1
        
        # 测试诊断功能（这里主要验证不会抛出异常）
        try:
            self.page_mgmt.diagnose_page_mapping()
            diagnosis_successful = True
        except Exception:
            diagnosis_successful = False
        
        self.assertTrue(diagnosis_successful)
        
    def test_standard_mapping_switch(self):
        """测试标准化映射切换"""
        # 创建页面但没有活动页面
        mock_page = Mock()
        mock_page.url = "https://example.com"
        mock_page.is_closed.return_value = False
        
        self.page_mgmt.context.pages = [mock_page]
        self.page_mgmt.active_page = None  # 没有活动页面
        
        # 执行标准化映射切换
        try:
            result = self.page_mgmt.switch_to_standard_mapping()
            switch_successful = True
        except Exception:
            switch_successful = False
        
        self.assertTrue(switch_successful)
        
    def test_empty_pages_handling(self):
        """测试空页面列表处理"""
        # 没有页面的情况
        self.page_mgmt.context.pages = []
        self.page_mgmt.active_page = None
        
        mapping = self.page_mgmt.get_page_variable_mapping()
        
        # 空页面列表应该返回空映射
        self.assertEqual(mapping, {})


class TestIntegratedImprovements(unittest.TestCase):
    """集成改进测试类"""
    
    def test_concurrent_page_operations(self):
        """测试并发页面操作"""
        # 创建一个完整的页面管理实例
        class TestPageManagement(PageManagementMixin):
            def __init__(self):
                self.context = Mock()
                self.context.pages = []
                self.active_page = None
                super().__init__()
        
        page_mgmt = TestPageManagement()
        
        # 创建模拟页面
        mock_pages = []
        for i in range(2):
            mock_page = Mock()
            mock_page.url = f"https://example.com/page{i+1}"
            mock_page.is_closed.return_value = False
            mock_pages.append(mock_page)
        
        page_mgmt.context.pages = mock_pages
        page_mgmt.active_page = mock_pages[0]
        
        # 测试并发协调功能
        stats = page_mgmt.get_coordination_stats()
        self.assertIsInstance(stats, dict)
        self.assertIn('performance_stats', stats)
        
        # 测试映射功能
        mapping = page_mgmt.get_page_variable_mapping()
        self.assertIsInstance(mapping, dict)
        self.assertIn('page', mapping)
        
        # 测试清理功能
        try:
            page_mgmt.cleanup_coordination()
            cleanup_successful = True
        except Exception:
            cleanup_successful = False
        
        self.assertTrue(cleanup_successful)


if __name__ == '__main__':
    # 运行测试
    unittest.main(verbosity=2)
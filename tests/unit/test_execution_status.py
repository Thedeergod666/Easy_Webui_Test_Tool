# tests/unit/test_execution_status.py
"""
执行状态系统单元测试

测试各种执行状态的处理逻辑和状态标记功能
"""
import unittest
import sys
import os

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, project_root)

from framework.utils.execution_status import (
    ExecutionStatus, StatusIcons, StatusMessages,
    format_status_message, is_try_status, is_skip_status, 
    is_end_status, is_normal_status, get_execution_status
)

class TestExecutionStatus(unittest.TestCase):
    """执行状态系统测试类"""
    
    def test_execution_status_constants(self):
        """测试执行状态常量定义"""
        self.assertEqual(ExecutionStatus.NORMAL, "")
        self.assertEqual(ExecutionStatus.SKIP, "skip")
        self.assertEqual(ExecutionStatus.TRY, "try")
        self.assertEqual(ExecutionStatus.END, "end")
    
    def test_status_icons(self):
        """测试状态图标定义"""
        self.assertEqual(StatusIcons.SUCCESS, "[PASS]")
        self.assertEqual(StatusIcons.FAILURE, "[FAIL]")
        self.assertEqual(StatusIcons.WARNING, "[WARN]")
        self.assertEqual(StatusIcons.END, "[END]")
    
    def test_status_messages(self):
        """测试状态消息定义"""
        self.assertEqual(StatusMessages.PASS, "[通过]")
        self.assertEqual(StatusMessages.FAIL, "[失败]")
        self.assertEqual(StatusMessages.SKIP, "[跳过]")
        self.assertEqual(StatusMessages.TRY_SUCCESS, "[尝试成功]")
        self.assertEqual(StatusMessages.TRY_FAIL_SKIP, "[尝试失败-已跳过]")
        self.assertEqual(StatusMessages.END, "[结束]")
    
    def test_format_status_message(self):
        """测试状态消息格式化"""
        # 基本消息格式化
        msg = format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS)
        self.assertEqual(msg, "[PASS] 结果: [通过]")
        
        # 带步骤ID的消息格式化
        msg = format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id="001")
        self.assertEqual(msg, "[PASS] 结果: [通过] - 步骤 001")
        
        # 带错误信息的消息格式化
        msg = format_status_message(StatusIcons.FAILURE, StatusMessages.FAIL, error="测试错误")
        self.assertEqual(msg, "[FAIL] 结果: [失败] - 测试错误")
        
        # 完整格式化
        msg = format_status_message(
            StatusIcons.WARNING, 
            StatusMessages.TRY_FAIL_SKIP, 
            step_id="002", 
            error="元素未找到"
        )
        self.assertEqual(msg, "[WARN] 结果: [尝试失败-已跳过] - 步骤 002 - 元素未找到")
    
    def test_is_try_status(self):
        """测试try状态检测"""
        self.assertTrue(is_try_status("try"))
        self.assertTrue(is_try_status("TRY"))
        self.assertTrue(is_try_status("  try  "))
        self.assertFalse(is_try_status("skip"))
        self.assertFalse(is_try_status(""))
        self.assertFalse(is_try_status("end"))
    
    def test_is_skip_status(self):
        """测试skip状态检测"""
        self.assertTrue(is_skip_status("skip"))
        self.assertTrue(is_skip_status("SKIP"))
        self.assertTrue(is_skip_status("  skip  "))
        self.assertFalse(is_skip_status("try"))
        self.assertFalse(is_skip_status(""))
        self.assertFalse(is_skip_status("end"))
    
    def test_is_end_status(self):
        """测试end状态检测"""
        self.assertTrue(is_end_status("end"))
        self.assertTrue(is_end_status("END"))
        self.assertTrue(is_end_status("  end  "))
        self.assertFalse(is_end_status("try"))
        self.assertFalse(is_end_status("skip"))
        self.assertFalse(is_end_status(""))
    
    def test_is_normal_status(self):
        """测试正常状态检测"""
        self.assertTrue(is_normal_status(""))
        self.assertTrue(is_normal_status("  "))
        self.assertTrue(is_normal_status(None))
        self.assertFalse(is_normal_status("try"))
        self.assertFalse(is_normal_status("skip"))
        self.assertFalse(is_normal_status("end"))
    
    def test_get_execution_status(self):
        """测试从测试步骤获取执行状态"""
        # 测试正常状态
        test_step = {"执行状态": ""}
        self.assertEqual(get_execution_status(test_step), "")
        
        # 测试try状态
        test_step = {"执行状态": "try"}
        self.assertEqual(get_execution_status(test_step), "try")
        
        # 测试skip状态
        test_step = {"执行状态": "skip"}
        self.assertEqual(get_execution_status(test_step), "skip")
        
        # 测试end状态
        test_step = {"执行状态": "end"}
        self.assertEqual(get_execution_status(test_step), "end")
        
        # 测试缺少执行状态字段
        test_step = {}
        self.assertEqual(get_execution_status(test_step), "")
        
        # 测试带空格的状态
        test_step = {"执行状态": "  TRY  "}
        self.assertEqual(get_execution_status(test_step), "try")

class TestExecutionStatusIntegration(unittest.TestCase):
    """执行状态系统集成测试类"""
    
    def test_complete_workflow(self):
        """测试完整的工作流程"""
        test_steps = [
            {"编号": "001", "关键字": "open", "执行状态": ""},
            {"编号": "002", "关键字": "verify", "执行状态": "try"},
            {"编号": "003", "关键字": "click", "执行状态": "skip"},
            {"编号": "004", "关键字": "close", "执行状态": "end"}
        ]
        
        # 模拟处理流程
        results = []
        for step in test_steps:
            status = get_execution_status(step)
            step_id = step.get("编号")
            
            if is_skip_status(status):
                msg = format_status_message(StatusIcons.SUCCESS, StatusMessages.SKIP, step_id)
                results.append(("SKIP", msg))
            elif is_end_status(status):
                msg = format_status_message(StatusIcons.END, StatusMessages.END, step_id)
                results.append(("END", msg))
                break  # 终止流程
            elif is_try_status(status):
                # 模拟try执行成功
                msg = format_status_message(StatusIcons.SUCCESS, StatusMessages.TRY_SUCCESS, step_id)
                results.append(("TRY_SUCCESS", msg))
            else:
                # 正常执行
                msg = format_status_message(StatusIcons.SUCCESS, StatusMessages.PASS, step_id)
                results.append(("NORMAL", msg))
        
        # 验证结果
        self.assertEqual(len(results), 4)
        self.assertEqual(results[0][0], "NORMAL")
        self.assertEqual(results[1][0], "TRY_SUCCESS")
        self.assertEqual(results[2][0], "SKIP")
        self.assertEqual(results[3][0], "END")
        
        # 验证消息格式
        self.assertIn("[PASS] 结果: [通过] - 步骤 001", results[0][1])
        self.assertIn("[PASS] 结果: [尝试成功] - 步骤 002", results[1][1])
        self.assertIn("[PASS] 结果: [跳过] - 步骤 003", results[2][1])
        self.assertIn("[END] 结果: [结束] - 步骤 004", results[3][1])

if __name__ == '__main__':
    unittest.main()

# framework/utils/execution_status.py
"""
执行状态系统 - 定义测试步骤的执行状态常量和消息

包含执行状态、状态图标和消息定义，用于统一管理测试步骤的状态标记。
"""

class ExecutionStatus:
    """执行状态常量定义"""
    NORMAL = ""       # 正常执行（空值或未指定）
    SKIP = "skip"     # 跳过执行
    TRY = "try"       # 尝试执行（失败不影响后续流程）
    END = "end"       # 终止流程

class StatusIcons:
    """状态图标定义"""
    SUCCESS = "✔️"    # 成功图标
    FAILURE = "❌"    # 失败图标
    WARNING = "⚠️"    # 警告图标
    END = "🔚"        # 结束图标

class StatusMessages:
    """状态消息定义"""
    PASS = "[通过]"
    FAIL = "[失败]"
    SKIP = "[跳过]"
    TRY_SUCCESS = "[尝试成功]"
    TRY_FAIL_SKIP = "[尝试失败-已跳过]"
    END = "[结束]"

def format_status_message(icon, message, step_id=None, error=None):
    """
    格式化状态消息
    
    Args:
        icon: 状态图标
        message: 状态消息
        step_id: 步骤ID（可选）
        error: 错误信息（可选）
    
    Returns:
        格式化后的状态消息字符串
    """
    base_msg = f"{icon} 结果: {message}"
    
    if step_id:
        base_msg += f" - 步骤 {step_id}"
    
    if error:
        base_msg += f" - {error}"
    
    return base_msg

def is_try_status(execution_status):
    """检查是否为尝试执行状态"""
    return str(execution_status).strip().lower() == ExecutionStatus.TRY

def is_skip_status(execution_status):
    """检查是否为跳过执行状态"""
    return str(execution_status).strip().lower() == ExecutionStatus.SKIP

def is_end_status(execution_status):
    """检查是否为终止执行状态"""
    return str(execution_status).strip().lower() == ExecutionStatus.END

def is_normal_status(execution_status):
    """检查是否为正常执行状态"""
    if execution_status is None:
        return True
    status = str(execution_status).strip().lower()
    return status == ExecutionStatus.NORMAL or status == ""

def get_execution_status(test_step):
    """
    从测试步骤中获取标准化的执行状态
    
    Args:
        test_step: 测试步骤字典
    
    Returns:
        标准化的执行状态字符串
    """
    return str(test_step.get('执行状态', '')).strip().lower()
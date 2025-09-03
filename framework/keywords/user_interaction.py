# -*- coding: utf-8 -*-
"""
用户交互模块
提供用户与页面元素交互相关的关键字
"""

import os
import pytest
from playwright.sync_api import Error as PlaywrightTimeoutError
from .base import _log_action


class UserInteractionMixin:
    """用户交互Mixin类
     
    提供用户与页面元素交互相关的方法实现。
    """
    
    @_log_action
    def hover(self, **kwargs):
        """
        [关键字] 将鼠标悬停在指定的元素上。
        常用于触发需要鼠标悬停才出现的菜单或提示。
        """
        description = kwargs.get('描述', '鼠标悬停')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.hover()
        print(f"✓ [{description}] 成功")
 
    def scroll_page(self, **kwargs):
        """
        [关键字] 在当前活动页面上模拟鼠标滚轮滚动。
        可用于处理懒加载页面或滚动到特定位置。
        数据内容: x轴滚动像素,y轴滚动像素 (e.g., "0,500" 表示向下滚动500px, "0,-500"表示向上)
        """
        scroll_data = str(kwargs.get('数据内容', '0,500')).strip()
        description = kwargs.get('描述', f'滚动页面 {scroll_data}')
        print(f"执行 [{description}]")
        try:
            delta_x, delta_y = map(int, scroll_data.split(','))
            self.active_page.mouse.wheel(delta_x, delta_y)
            print(f"✓ [{description}] 成功")
        except ValueError:
            pytest.fail(f"滚动数据格式错误: '{scroll_data}', 期望格式为 'x,y' (例如 '0,500')")
 
    @_log_action
    def drag_and_drop(self, **kwargs):
        """
        [关键字] 将一个元素拖拽到另一个元素上。
        目标对象/定位方式:  描述的是【源元素】。
        数据内容:          描述的是【目标元素】的CSS选择器或XPath。
        """
        description = kwargs.get('描述', '拖拽元素')
        print(f"执行 [{description}]")
        source_locator = self._get_locator(**kwargs)
        
        target_selector = str(kwargs.get('数据内容', '')).strip()
        if not target_selector:
            pytest.fail("drag_and_drop 关键字的 '数据内容' 列必须提供目标元素的选择器。")
            
        print(f"  > 源元素: {source_locator}")
        print(f"  > 目标元素选择器: {target_selector}")
 
        # Playwright的 drag_to 需要一个 Locator 作为目标
        target_locator = self.active_page.locator(target_selector)
        
        source_locator.drag_to(target_locator)
        print(f"✓ [{description}] 成功")
 
    def click_at_position(self, **kwargs):
        """
        [高级][关键字] 在元素的特定相对位置或绝对坐标上点击。
        可用于点击进度条、Canvas图表等。
        - 如果提供了定位器:
            数据内容: "x=0.5, y=0.5" (相对坐标, 0.5代表中心点)
        - 如果未提供定位器:
            数据内容: "x=800, y=600" (绝对视口坐标)
        """
        position_data = str(kwargs.get('数据内容', '')).strip()
        description = kwargs.get('描述', f'在位置 {position_data} 点击')
        print(f"执行 [{description}]")
        
        try:
            # 解析 x, y 坐标
            pos_dict = dict(item.split("=") for item in position_data.replace(" ", "").split(','))
            x_pos = float(pos_dict['x'])
            y_pos = float(pos_dict['y'])
        except Exception:
            pytest.fail(f"位置数据格式错误: '{position_data}', 期望格式为 'x=数值,y=数值'")
        
        locator_type = str(kwargs.get('定位方式', '')).lower()
        
        if locator_type:
            # 模式一: 点击元素的相对位置
            print(f"  > 相对定位模式: 在元素内 ({x_pos*100}%, {y_pos*100}%) 位置点击")
            locator = self._get_locator(**kwargs)
            locator.click(position={'x': x_pos, 'y': y_pos})
        else:
            # 模式二: 点击页面的绝对坐标
            print(f"  > 绝对定位模式: 在页面视口 ({x_pos}px, {y_pos}px) 位置点击")
            self.active_page.mouse.click(int(x_pos), int(y_pos))
            
        print(f"✓ [{description}] 成功")

    @_log_action
    def click(self, **kwargs):
        """
        [关键字] 在找到的元素上执行单击操作。
        操作自带智能等待，会等待元素可见、可点击。
        """
        description = kwargs.get('描述', '点击操作')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.click()
        print(f"✓ [{description}] 成功")

    @_log_action
    def press(self, **kwargs):
        """
        [关键字] 在指定的元素上模拟按下单个键盘按键。
        数据内容: 要按下的键名，如 "Tab", "Enter", "ArrowDown", "a", "Control+C"。
        """
        key_to_press = str(kwargs.get('数据内容', ''))
        description = kwargs.get('描述', f'模拟按键 {key_to_press}')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.press(key_to_press)
        print(f"✓ [{description}] 成功")

    @_log_action
    def check(self, **kwargs):
        """
        [关键字] 选中复选框或单选框。
        操作自带智能等待，会等待元素可见、可交互。
        如果元素已经是选中状态，则不会重复选中。
        """
        description = kwargs.get('描述', '选中复选框/单选框')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.check()
        print(f"✓ [{description}] 成功")

    @_log_action
    def on_input(self, **kwargs):
        """
        [关键字] 向输入框中填入文本。
        此操作会先清空输入框，然后填入新内容，比逐字输入更稳定快速。
        数据内容: 要输入的文本。
        """
        text_to_fill = str(kwargs.get('数据内容', ''))
        description = kwargs.get('描述', f'输入 "{text_to_fill}"')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.fill(text_to_fill)
        print(f"✓ [{description}] 成功")
    
    def clear_input(self, **kwargs):
        """
        这是一个兼容旧用例的过渡方法。
        [关键字] 清空指定的输入框。
        注意：'on_input'关键字已包含清空功能，此关键字仅用于适配旧框架测试数据。
        """
        description = kwargs.get('描述', '清空输入框')
        print(f"执行 [{description}]")
        locator = self._get_locator(**kwargs)
        locator.clear()
        print(f"✓ [{description}] 成功")

    def upload_file(self, **kwargs):
        """
        [关键字] 在文件上传类型的input元素上设置要上传的文件。
        数据内容: 要上传的文件的本地路径 (可以是相对或绝对路径)。
        """
        file_path = str(kwargs.get('数据内容', ''))
        if not file_path:
            pytest.fail("upload_file 关键字需要在 '数据内容' 列提供文件路径。")
            
        description = kwargs.get('描述', f'上传文件 {os.path.basename(file_path)}')
        print(f"执行 [{description}]")
        
        locator = self._get_locator(**kwargs)
        
        # 检查文件是否存在
        if not os.path.isabs(file_path):
            # 如果是相对路径，相对于项目根目录
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            file_path = os.path.join(project_root, file_path)
        
        if not os.path.exists(file_path):
            pytest.fail(f"上传失败：文件 '{file_path}' 不存在。")
            
        locator.set_input_files(file_path)
        print(f"✓ [{description}] 成功")
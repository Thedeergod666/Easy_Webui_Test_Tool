# 动态URL匹配功能使用指南

## 概述

本功能为playwright_ui自动化测试框架增加了强大的动态URL匹配能力，支持通配符、正则表达式等模式匹配，使测试脚本能够应对URL参数变化的场景。

## 主要特性

### 1. 多种匹配模式支持

#### 精确匹配（默认）
```excel
关键字        | 数据内容
open         | https://example.com/exact/path
```

#### 通配符匹配
```excel
关键字        | 数据内容
open         | https://example.com/*
switch_to_page| *example.com*
close_page   | https://*/product/123
```

#### 正则表达式匹配
```excel
关键字        | 数据内容
open         | {regex:https://agent\.teleai\.com\.cn/square/market-chat/\w+\?.*}
close_page   | {regex:.*product/\d+.*}
```

#### 部分匹配
```excel
关键字        | 数据内容
switch_to_page| agent.teleai.com.cn
close_page   | market-chat
```

### 2. 智能降级策略

当使用模式匹配未找到匹配页面时，系统会：
1. 自动提取基础URL
2. 导航到基础URL
3. 提供详细的匹配过程日志

### 3. 增强的关键字支持

#### open关键字
- 优先在已打开页面中查找匹配
- 找到匹配页面时自动切换
- 未找到时降级到基础URL导航

#### close_page关键字
- 支持URL模式匹配关闭页面
- 支持多种识别方式：页码、完整URL、URL模式

#### switch_to_page关键字
- 支持通过URL模式切换页面
- 提供智能页面查找和错误提示

### 4. 配置与诊断

#### 配置URL匹配行为
```excel
关键字                  | 数据内容
configure_url_matching | enable_pattern_matching=true strict_matching=false
```

#### 诊断URL匹配问题
```excel
关键字                | 数据内容
diagnose_url_matching | {regex:https://agent\.teleai\.com\.cn/.*}
```

## 实际使用示例

### 场景1：动态会话ID的页面操作
```excel
步骤 | 关键字        | 数据内容
1   | open         | https://agent.teleai.com.cn/square/market-chat/*
2   | input        | 用户输入内容
3   | click        | 发送按钮
```

### 场景2：批量关闭特定模式的页面
```excel
步骤 | 关键字        | 数据内容
1   | close_page   | *temp*
2   | close_page   | {regex:.*test.*}
```

### 场景3：在多个相似页面间切换
```excel
步骤 | 关键字         | 数据内容
1   | switch_to_page | *product/123*
2   | input         | 产品名称
3   | switch_to_page | *product/456*
4   | input         | 产品名称
```

## 配置选项

| 配置项 | 默认值 | 描述 |
|--------|--------|------|
| enable_pattern_matching | true | 启用/禁用模式匹配功能 |
| strict_matching | false | 严格匹配模式，禁用降级策略 |
| case_sensitive | false | URL匹配是否区分大小写 |
| max_pattern_length | 500 | URL模式最大长度限制 |

## 日志输出示例

```
执行 [打开页面]: {regex:https://agent\.teleai\.com\.cn/square/market-chat/\w+\?.*}
  [动态URL匹配] 检测到URL模式，开始查找匹配页面...
    [URL匹配] 开始在 3 个页面中查找匹配: {regex:https://agent\.teleai\.com\.cn/square/market-chat/\w+\?.*}
    [URL匹配] ✓ 正则表达式匹配成功: https://agent\.teleai\.com\.cn/square/market-chat/\w+\?.* -> https://agent.teleai.com.cn/square/market-chat/abc123?param=value (评分: 0.85)
    [URL匹配] ✓ 找到 1 个匹配页面，最佳匹配:
        页面 2: https://agent.teleai.com.cn/square/market-chat/abc123?param=value
        匹配类型: regex
        匹配评分: 0.85
  [动态URL匹配] ✓ 找到匹配页面，切换到该页面
  [动态URL匹配] ✓ 已切换到页面 2: https://agent.teleai.com.cn/square/market-chat/abc123?param=value
SUCCESS [Open Page] 使用已存在页面，匹配类型: regex
```

## 向后兼容性

- 所有现有测试用例无需修改即可正常运行
- 新功能为可选特性，不影响现有功能
- 普通URL自动绕过模式匹配逻辑
- 传统的页码和精确URL操作完全保持原有行为

## 性能考虑

- 缓存编译后的正则表达式，避免重复编译
- 匹配成功后立即返回，避免不必要的检查
- 对URL模式长度和复杂度进行限制，防止性能问题
- 在大量页面环境下性能经过测试验证

## 故障排除

### 常见问题

1. **正则表达式匹配失败**
   - 检查正则表达式语法是否正确
   - 使用 `diagnose_url_matching` 诊断匹配问题
   - 注意转义特殊字符

2. **通配符匹配不准确**
   - 确认通配符位置是否合理
   - 避免过多通配符影响性能
   - 考虑使用更精确的正则表达式

3. **页面切换失败**
   - 确认页面确实存在且未关闭
   - 检查URL模式是否与实际页面URL匹配
   - 查看详细的匹配过程日志

### 调试技巧

1. 使用 `get_url_matching_config` 查看当前配置
2. 使用 `diagnose_url_matching` 诊断特定模式
3. 查看控制台输出的详细匹配日志
4. 在测试环境中逐步验证匹配逻辑

## 总结

动态URL匹配功能大大增强了playwright_ui框架的灵活性和实用性，特别适用于：

- 包含动态参数的现代Web应用
- 需要在多个相似页面间操作的测试场景
- 需要批量处理特定模式页面的自动化任务
- 希望减少URL变化带来的测试维护成本的项目

通过合理使用这些功能，可以显著提高测试脚本的稳定性和可维护性。
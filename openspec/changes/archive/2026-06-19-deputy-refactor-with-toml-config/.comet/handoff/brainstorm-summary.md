# Brainstorm Summary

- Change: deputy-refactor-with-toml-config
- Date: 2026-06-18

## 确认的技术方案

### 架构选择：直接移植 mihomo-config 架构
- 完全基于 mihomo-config 的代码结构和设计模式
- 保留核心功能：传输链路、验证机制、模板渲染
- 直接复用 mihomo-config 的模板系统（基于占位符替换）

### 已确认的设计决策
- **节点配置优先级**: 订阅源为主，静态节点为辅
- **失败策略**: 部分失败也发布，在发布说明中标注问题源
- **验证性能**: 30并发，3秒超时，类似 mihomo-config 配置
- **发布频率**: 定时 3 小时 + 手动触发 + 变更触发
- **模板系统**: 使用单一模板（config.template.yaml），输出单一配置（config.yaml）

### 核心架构组件
**传输层模块 (`fetch_transport.py`)**:
- `TransportChain`: 管理传输链路的协调器
- `CloudscraperTransport`: 处理 Cloudflare challenge
- `RequestsTransport`: 标准 HTTP 请求
- `CurlCffiTransport`: 浏览器指纹伪装

**主同步脚本 (`sync_nodes.py`)**:
- TOML 配置加载和解析
- 并发节点获取和验证
- 质量统计和报告生成
- 单一模板渲染（输出 config.yaml）

**模板系统**（直接复用 mihomo-config）:
- 使用单一模板：config.template.yaml
- 占位符：`{LOCAL_PROXIES}`, `{SUB_PROXIES}`, `{PROXIES}`, `{NODE_SELECT_LIST}`, `{DIALER_LIST}`
- 正则表达式匹配：`r"\{([A-Z_][A-Z0-9_]*)\}"`
- 输出单一 config.yaml 文件

### 数据流设计
```
nodes.toml → 解析和验证 → 并发获取节点 
    ↓
节点验证管道 → TCP探测 → HTTP检查 → 延迟测试
    ↓
质量统计和排序 → 生成统计数据 → 节点排序
    ↓
单一模板渲染 → config.yaml → YAML输出
    ↓
GitHub Releases → 版本管理 → 发布说明
```

## 关键取舍与风险

### 关键技术决策
1. **架构选择**: 直接移植 mihomo-config 架构，最大化复用验证过的设计
2. **模板简化**: 使用单一模板而非多模板，降低维护复杂度
3. **失败容错**: 部分失败仍发布，保证服务连续性
4. **性能平衡**: 30并发/3秒超时，平衡性能和准确性

### 主要技术风险
1. **大规模节点验证的性能影响** → 30并发限制，3秒超时，监控执行时间
2. **传输链路稳定性** → 三层 fallback，详细错误日志，监控成功率
3. **GitHub Actions 执行时间限制** → 优化验证逻辑，分阶段处理，监控各阶段耗时

### 技术取舍
- **简单性 vs 功能完整性**: 选择简单性，使用单一模板
- **性能 vs 准确性**: 选择平衡，30并发/3秒超时
- **可靠性 vs 可用性**: 选择可用性，部分失败仍发布
- **开发速度 vs 风险控制**: 选择风险控制，直接移植成熟架构

## 测试策略

### 单元测试
- **传输层测试**: CloudscraperTransport, RequestsTransport, CurlCffiTransport 的独立功能测试
- **配置解析测试**: TOML 文件解析、验证、错误处理
- **节点验证测试**: TCP探测、HTTP检查、延迟测试的独立测试
- **模板渲染测试**: _safe_format_map 函数的正确性和边界条件

### 集成测试
- **完整流程测试**: 从配置加载到 GitHub Releases 发布的端到端测试
- **模板渲染测试**: 单一模板渲染，验证输出 YAML 的正确性
- **错误处理测试**: 各种失败场景的处理和恢复机制
- **并发控制测试**: 验证并发限制和资源管理

### 端到端测试
- **真实环境测试**: 使用真实订阅源验证完整流程
- **配置输出验证**: 验证生成的 config.yaml 格式和内容正确性
- **边界条件测试**: 测试极端情况（空节点、全部失败、网络问题等）
- **性能测试**: 验证在大量节点情况下的性能表现

### 测试覆盖重点
1. **传输链路的 fallback 机制**
2. **节点验证的准确性和性能**
3. **模板渲染的正确性**
4. **GitHub Releases 发布的可靠性**
5. **错误处理的完整性**

## Spec Patch

需要补充的验收场景：

### github-releases-distribution/spec.md
**需要补充的验收场景**:
- 场景：单一配置文件发布
  - **WHEN** 系统创建 GitHub Release
  - **THEN** 只发布单一的 config.yaml 文件
  - **AND** 不发布其他配置文件

**其他说明**: 当前 OpenSpec delta specs 已经覆盖了大部分需求，只需要补充上述关于单一配置文件发布的验收场景。注意：原提案中的"multi-platform-config" capability 不再需要，应该从提案中移除。
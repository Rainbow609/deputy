## Context

**当前状态**: deputy 项目使用简单的 Python 脚本 (`get_node_list.py`) 从多个订阅源下载节点配置并合并到不同的配置模板中。现有的架构功能有限，缺乏节点质量控制、验证机制和现代化的发布流程。

**技术约束**: 
- 目标项目是公开的节点聚合项目，汇总多个开源节点的配置
- 不需要环境变量管理，节点配置直接存储在仓库中
- 需要支持多平台配置生成（桌面、移动、Magisk）
- 必须确保节点质量和可用性

**利益相关者**: 
- 项目维护者：需要可靠的节点质量控制和自动化维护流程
- 终端用户：需要高质量的节点配置和稳定的更新机制
- 节点提供者：需要正确的节点引用和验证机制

## Goals / Non-Goals

**Goals:**
- 建立健壮的节点配置管理系统，采用 TOML 格式统一管理静态节点和订阅源
- 实现完整的节点验证机制，包括 TCP 连通性、HTTP 健康检查和延迟测试
- 建立现代化的发布机制，使用 GitHub Releases 替代 git commit
- 支持多平台配置文件生成，基于 mihomo-config 的模板系统
- 实现自动化的 CI/CD 流程，确保配置质量和发布效率
- 提供节点质量监控和统计分析能力

**Non-Goals:**
- 保持与现有 deputy 用户的兼容性（完全重构，不考虑向后兼容）
- 支持 mihomo-config 中的所有高级功能（如 Gist 发布）
- 环境变量管理和敏感信息处理（公开项目，配置文件直接存储）
- 复杂的权限管理和用户认证系统

## Decisions

### 1. 架构设计：基于 mihomo-config 的传输链路和验证机制

**决策**: 采用 mihomo-config 的传输链路架构 (`cloudscraper → requests → curl_cffi`) 和节点验证机制。

**理由**:
- mihomo-config 的传输链路已经过实战验证，能够有效处理反爬和连接问题
- TCP 探测机制简单可靠，能够准确判断节点可用性
- 延迟测试和排序机制有助于提升用户体验
- 架构成熟，可以减少开发和测试成本

**替代方案**: 
- 仅使用 requests 库：无法处理 Cloudflare challenge 等反爬机制
- 自建传输机制：开发成本高，稳定性未知

### 2. 配置格式：统一 TOML 配置文件

**决策**: 使用单一的 `nodes.toml` 文件管理所有节点配置，包括静态节点和订阅源。

**理由**:
- TOML 格式清晰易读，适合配置文件
- 单一文件便于维护和理解
- 混合配置支持灵活的节点来源管理
- 与 mihomo-config 的配置风格保持一致

**替代方案**:
- 多个 TOML 文件：增加管理复杂度
- 继续使用 YAML：不符合用户需求

### 3. 发布机制：GitHub Releases

**决策**: 使用 GitHub Releases 替代 git commit 作为配置发布机制。

**理由**:
- Releases 提供版本控制和变更追踪
- 用户可以方便地下载特定版本的配置
- 发布说明可以包含节点统计和变更信息
- 支持多文件发布（多个平台的配置文件）

**替代方案**:
- 继续使用 git commit：缺乏版本控制，用户体验差
- Gist 发布：不适合多文件发布，缺乏版本管理

### 4. 节点验证：多层次验证机制

**决策**: 实现 TCP 连通性探测、HTTP 健康检查和延迟测试的多层次验证。

**理由**:
- TCP 探测快速准确，适合初步筛选
- HTTP 健康检查确保节点功能完整
- 延迟测试提供用户体验相关指标
- 多层次验证提高节点质量保证

**替代方案**:
- 仅 TCP 探测：可能遗漏功能问题
- 仅 HTTP 检查：性能开销大

### 5. 多平台支持：模板化配置生成

**决策**: 基于 mihomo-config 的模板系统，通过模板变量生成多平台配置。

**理由**:
- 模板系统成熟可靠
- 减少代码重复，提高维护效率
- 支持平台特定优化
- 与 mihomo-config 保持一致

**替代方案**:
- 手动维护多平台配置：维护成本高，容易出错

## Risks / Trade-offs

### 风险 1：传输链路稳定性

**风险**: 第三方传输库（curl_cffi）可能存在兼容性或稳定性问题。

**缓解措施**: 
- 实现 fallback 机制，curl_cffi 失败时回退到 requests
- 在 GitHub Actions 中进行充分测试
- 监控传输成功率，及时发现问题

### 风险 2：节点验证性能影响

**风险**: 大量节点的并发验证可能导致性能问题或超时。

**缓解措施**:
- 实现并发控制，限制同时验证的节点数量
- 设置合理的超时时间（如 3 秒）
- 实现缓存机制，避免重复验证

### 风险 3：发布频率控制

**风险**: 频繁的 GitHub Releases 可能造成版本泛滥。

**缓解措施**:
- 只在有实际更新时发布新版本
- 使用时间戳版本号便于管理
- 在 Release 说明中提供详细的变更信息

### 风险 4：用户迁移成本

**风险**: 完全重构可能导致用户需要重新配置订阅地址。

**缓解措施**:
- 在 README 中提供清晰的迁移指南
- 在 Release 说明中突出显示重大变更
- 考虑在新旧版本之间提供过渡期

## Migration Plan

**部署步骤**:

1. **开发阶段**:
   - 重写 `get_node_list.py` 为 `sync_nodes.py`
   - 创建 `nodes.toml` 配置文件
   - 实现传输链路和节点验证机制
   - 创建配置模板系统

2. **测试阶段**:
   - 在本地环境测试完整流程
   - 验证节点验证机制的准确性
   - 测试多平台配置生成
   - 验证 GitHub Actions 工作流

3. **部署阶段**:
   - 更新 GitHub Actions 工作流
   - 首次运行生成配置文件
   - 创建第一个 GitHub Release
   - 更新 README 文档

4. **监控阶段**:
   - 监控节点验证成功率
   - 监控传输链路稳定性
   - 收集用户反馈

**回滚策略**:
- 保留原有的 `get_node_list.py` 脚本作为备份
- 如果新架构出现问题，可以快速恢复到旧版本
- Git 历史记录提供完整的版本回退能力

## Implementation Divergence

**Recorded during verify phase (2026-06-19)**: User requirement is single-platform output. The following delta specs in `openspec/changes/deputy-refactor-with-toml-config/specs/` describe capabilities **not implemented** in this change and should NOT be synchronized to main specs during archive. They are preserved in the change delta specs as future capabilities, deferred to a follow-up change.

### Deferred Specs (brainstormed but out of scope)

- **`multi-platform-config/`** — Desktop/Mobile/Magisk platform generation. Proposal explicitly states "采用 mihomo-config 的单一模板系统，输出单一配置文件（config.yaml）" and "发布单一配置文件" — this capability conflicts with the user's stated requirement. The earlier draft Decision #5 ("多平台支持：模板化配置生成") was brainstormed under a different interpretation; the actual proposal commitment is single-platform. **Excluded from archive sync.**

- **`node-verification` partial** — Requirement "HTTP health checking" not implemented. Current verification is TCP-only (`scripts/node_verifier.py::_tcp_check`). Module docstring mentions HTTP but no `http_health_check` function exists. **Excluded from archive sync.**

- **`quality-metrics` partial** — 4 of 7 requirements not implemented: "Regional distribution analysis", "Node quality scoring", "Historical data tracking", "Alert threshold management". Proposal only commits to "存活率、延迟分布等指标". **Excluded from archive sync.**

### Decision

Archive should sync only the implemented subset of delta specs:
- `toml-node-config` ✅ (full)
- `node-verification` ✅ (partial — TCP only; HTTP deferred)
- `github-releases-distribution` ✅ (full; single-file attachment is intentional)
- `quality-metrics` ✅ (partial — survival + latency stats + release notes; regional/scoring/history/alerts deferred)
- `multi-platform-config` ❌ **excluded from sync**

This divergence is approved by user (2026-06-19 verify checkpoint): "用户需求就是单平台".

## Open Questions

1. **GitHub Actions 权限配置**: 创建 GitHub Releases 需要什么具体的权限配置？
2. **节点验证并发控制**: 最佳的并发数量是多少，如何在性能和稳定性之间平衡？
3. **版本号策略**: 时间戳版本号是否足够，还是需要语义化版本控制？
4. **节点冲突处理**: 当静态节点和订阅节点名称冲突时，如何处理？
5. **错误报告机制**: 如何向用户报告节点验证失败的具体原因？
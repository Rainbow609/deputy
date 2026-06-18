# Comet Design Handoff

- Change: deputy-refactor-with-toml-config
- Phase: design
- Mode: compact
- Context hash: 169cf8295983fd5f05ba2f93d2d4f4e5e125e7f90c06e7bf8227659925f48236

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/deputy-refactor-with-toml-config/proposal.md

- Source: openspec/changes/deputy-refactor-with-toml-config/proposal.md
- Lines: 1-50
- SHA256: 6b23dbca188c5a030db4d8f7fcbf56deaf610f228605aeace6d29a1ed0706d45

```md
## Why

当前的 deputy 项目架构简单但功能有限：只能下载和合并 proxy providers 配置，缺乏节点质量控制、验证机制和现代化的发布流程。随着节点数量增加和用户需求提升，需要建立更健壮的配置生成系统，确保节点质量、提高维护效率，并采用更专业的分发机制。

## What Changes

基于 mihomo-config 完全重构 deputy 项目，建立自动化的节点配置生成和发布系统：

- **BREAKING**: 配置格式从 YAML 改为 TOML，采用单一配置文件（nodes.toml）混合管理静态节点和订阅源
- **BREAKING**: 发布机制从 git commit 改为 GitHub Releases，每次更新生成带时间戳的版本号
- 新增完整的节点验证机制：TCP连通性探测、HTTP健康检查、延迟测试和排序
- 实现健壮的传输链路：cloudscraper → requests → curl_cffi，自动处理反爬和连接问题
- 采用 mihomo-config 的单一模板系统，输出单一配置文件（config.yaml）
- 新增节点质量监控和统计报告功能
- 建立 CI/CD 自动化流程，有更新时自动发布新版本

## Capabilities

### New Capabilities
- `toml-node-config`: TOML 格式的统一节点配置管理，支持静态节点和订阅源混合配置
- `node-verification`: 综合节点验证机制，包括 TCP 连通性、HTTP 健康检查和延迟测试
- `github-releases-distribution`: 基于 GitHub Releases 的自动化版本发布机制，发布单一配置文件
- `quality-metrics`: 节点质量监控和统计分析，提供存活率、延迟分布等指标

### Modified Capabilities
- 无现有 capabilities 需要修改（完全重构）

## Impact

**代码影响**:
- 完全重写 `get_node_list.py` 为 `sync_nodes.py`，采用 mihomo-config 的架构设计
- 新增 `nodes.toml` 配置文件，替代现有的 `proxy-providers.yaml`
- 重构配置模板系统，采用 mihomo-config 的模板设计模式
- 新增传输层模块 (`fetch_transport.py`) 处理反爬和连接问题
- 重构 GitHub Actions 工作流，支持 GitHub Releases 发布

**API 影响**:
- 节点配置 API 从 YAML 改为 TOML 格式
- 新增节点验证和质量监控 API
- 发布 API 从 git push 改为 GitHub Releases API

**依赖影响**:
- 新增 Python 依赖：`cloudscraper`、`curl_cffi`、`tomllib`（Python 3.11+ 内置）
- 采用 `uv` 作为 Python 包管理工具
- 新增 GitHub Actions 依赖：`softprops/action-gh-release`（用于创建 Releases）

**系统影响**:
- 用户需要更新订阅地址（从 GitHub 文件改为 GitHub Releases）
- CI/CD 流程完全重构，增加质量检查和统计报告
- 发布频率从定时改为按需（有更新才发布）
- 新增版本控制和变更追踪机制```

## openspec/changes/deputy-refactor-with-toml-config/design.md

- Source: openspec/changes/deputy-refactor-with-toml-config/design.md
- Lines: 1-178
- SHA256: 2d83c541c5dfd7508b52236cfda415e78f4223c93b3134e0c98eac0dc8d9c98f

[TRUNCATED]

```md
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
```

Full source: openspec/changes/deputy-refactor-with-toml-config/design.md

## openspec/changes/deputy-refactor-with-toml-config/tasks.md

- Source: openspec/changes/deputy-refactor-with-toml-config/tasks.md
- Lines: 1-110
- SHA256: 3ec66520cda4793e52f245ceb02d1795c7596fa921b6e9b2e2c85c02cfcf9d87

[TRUNCATED]

```md
## 1. 项目基础设施设置

- [ ] 1.1 安装和配置 `uv` Python 包管理工具
- [ ] 1.2 创建 `pyproject.toml` 文件，定义项目依赖
- [ ] 1.3 添加必要的 Python 依赖：`cloudscraper`、`curl_cffi`、`PyYAML`、`tomllib`（Python 3.11+）
- [ ] 1.4 创建项目目录结构：`scripts/`、`templates/`、`tests/`
- [ ] 1.5 配置 `.github/workflows/` 目录用于 CI/CD

## 2. TOML 配置系统实现

- [ ] 2.1 创建 `nodes.toml` 配置文件模板和示例
- [ ] 2.2 实现 TOML 配置文件解析模块
- [ ] 2.3 实现静态节点配置解析和验证
- [ ] 2.4 实现订阅源配置解析和验证
- [ ] 2.5 实现配置验证和错误处理机制
- [ ] 2.6 实现节点名称冲突解决机制

## 3. 传输层实现

- [ ] 3.1 创建 `fetch_transport.py` 模块，实现传输链路基础架构
- [ ] 3.2 实现 `CloudscraperTransport` 传输类
- [ ] 3.3 实现 `RequestsTransport` 传输类
- [ ] 3.4 实现 `CurlCffiTransport` 传输类
- [ ] 3.5 实现 `TransportChain` 传输链管理器
- [ ] 3.6 实现传输失败检测和自动 fallback 机制
- [ ] 3.7 实现反爬虫挑战检测和处理

## 4. 节点验证系统实现

- [ ] 4.1 实现 TCP 连通性探测模块
- [ ] 4.2 实现 HTTP 健康检查模块
- [ ] 4.3 实现延迟测试和测量模块
- [ ] 4.4 实现并发验证处理机制
- [ ] 4.5 实现验证结果聚合和状态判断
- [ ] 4.6 实现超时和重试机制
- [ ] 4.7 实现节点质量评分算法

## 5. 多平台配置生成实现

- [ ] 5.1 创建基于 mihomo-config 的配置模板系统
- [ ] 5.2 创建桌面平台配置模板 `config_desktop.template.yaml`
- [ ] 5.3 创建移动平台配置模板 `config_mobile.template.yaml`
- [ ] 5.4 创建 Magisk 平台配置模板 `config_magisk.template.yaml`
- [ ] 5.5 实现模板变量替换和渲染引擎
- [ ] 5.6 实现多平台并发配置生成
- [ ] 5.7 实现配置文件验证机制

## 6. 质量监控和统计系统实现

- [ ] 6.1 实现节点存活率计算模块
- [ ] 6.2 实现区域分布分析模块
- [ ] 6.3 实现延迟统计和分布分析模块
- [ ] 6.4 实现变更跟踪和报告模块
- [ ] 6.5 实现统计数据格式化和输出
- [ ] 6.6 实现历史数据存储和趋势分析
- [ ] 6.7 实现告警阈值管理机制

## 7. GitHub Releases 发布机制实现

- [ ] 7.1 实现时间戳版本号生成模块
- [ ] 7.2 实现 GitHub Releases API 集成
- [ ] 7.3 实现变更检测和条件发布机制
- [ ] 7.4 实现发布说明自动生成
- [ ] 7.5 实现多文件发布附件管理
- [ ] 7.6 实现发布失败处理和错误报告

## 8. 核心脚本实现

- [ ] 8.1 重写主同步脚本 `sync_nodes.py`
- [ ] 8.2 实现完整的配置同步流程编排
- [ ] 8.3 实现节点处理管道：获取 → 验证 → 排序 → 合并
- [ ] 8.4 实现配置生成和输出管理
- [ ] 8.5 实现统计报告生成和输出

## 9. GitHub Actions 工作流实现

- [ ] 9.1 创建 `.github/workflows/sync-and-release.yml` 工作流文件
- [ ] 9.2 配置定时触发器（替代原有 30 分钟 cron）
- [ ] 9.3 配置手动触发器 `workflow_dispatch`
- [ ] 9.4 配置 push 触发器（检测脚本和配置变更）
```

Full source: openspec/changes/deputy-refactor-with-toml-config/tasks.md

## openspec/changes/deputy-refactor-with-toml-config/specs/github-releases-distribution/spec.md

- Source: openspec/changes/deputy-refactor-with-toml-config/specs/github-releases-distribution/spec.md
- Lines: 1-120
- SHA256: 0bdf65efd9184338d1378bc4964c381c6770c0941723ba7b256100d571f3e9a0

[TRUNCATED]

```md
# GitHub Releases Distribution

## ADDED Requirements

### Requirement: GitHub Release creation
The system SHALL create GitHub Releases for publishing configuration files.

#### Scenario: Create new release
- **WHEN** the system has new configuration files to publish
- **THEN** the system creates a new GitHub Release
- **AND** the system uses timestamp-based version naming

#### Scenario: Release with configuration files
- **WHEN** creating a GitHub Release
- **THEN** the system attaches the single generated configuration file (config.yaml)
- **AND** the system includes comprehensive release notes

#### Scenario: Single configuration file publication
- **WHEN** the system creates a GitHub Release
- **THEN** the system publishes only one configuration file (config.yaml)
- **AND** the system does not create multiple platform-specific files
- **AND** the single config.yaml is suitable for various platforms (desktop, mobile, Magisk)

### Requirement: Timestamp-based versioning
The system SHALL use timestamp-based versioning for GitHub Releases.

#### Scenario: Version naming format
- **WHEN** the system creates a new release
- **THEN** the system uses format `vYYYY-MM-DD-HHMMSS` for version naming
- **AND** the system uses UTC timezone for timestamp generation

#### Scenario: Version uniqueness
- **WHEN** creating multiple releases in quick succession
- **THEN** each version name is unique based on exact timestamp
- **AND** the system ensures no duplicate version names

### Requirement: Conditional release creation
The system SHALL only create releases when there are actual configuration changes.

#### Scenario: No configuration changes
- **WHEN** the system runs but configuration files have no changes
- **THEN** the system does not create a new release
- **AND** the system logs that no changes were detected

#### Scenario: Configuration changes detected
- **WHEN** the system detects changes in configuration files
- **THEN** the system creates a new release with updated files
- **AND** the system includes change information in release notes

### Requirement: Release notes generation
The system SHALL generate comprehensive release notes for each release.

#### Scenario: Node statistics
- **WHEN** generating release notes
- **THEN** the system includes total node count
- **AND** the system includes regional distribution statistics
- **AND** the system includes node survival rate

#### Scenario: Latency statistics
- **WHEN** generating release notes
- **THEN** the system includes average latency
- **AND** the system includes fastest and slowest node information
- **AND** the system includes latency distribution data

#### Scenario: Change documentation
- **WHEN** generating release notes
- **THEN** the system includes new nodes added
- **AND** the system includes failed nodes removed
- **AND** the system includes configuration changes

### Requirement: Multi-file release attachment
The system SHALL attach multiple configuration files to each release.

#### Scenario: All platform configurations
- **WHEN** creating a release
- **THEN** the system attaches desktop, mobile, and Magisk configuration files
- **AND** each file is named appropriately for its platform

#### Scenario: Additional metadata files
- **WHEN** creating a release
```

Full source: openspec/changes/deputy-refactor-with-toml-config/specs/github-releases-distribution/spec.md

## openspec/changes/deputy-refactor-with-toml-config/specs/multi-platform-config/spec.md

- Source: openspec/changes/deputy-refactor-with-toml-config/specs/multi-platform-config/spec.md
- Lines: 1-93
- SHA256: fac5c61ecf56a0ccfdf68f21c3430f6b53ad09ceda7e28dbfd3f603ccc01e380

[TRUNCATED]

```md
# Multi-Platform Configuration Generation

## ADDED Requirements

### Requirement: Desktop platform configuration generation
The system SHALL generate optimized configuration files for desktop platforms.

#### Scenario: Desktop configuration generation
- **WHEN** the system generates configuration for desktop platforms
- **THEN** the system uses desktop-specific optimizations and settings
- **AND** the system outputs the configuration to `config_desktop.yaml`

#### Scenario: Desktop-specific features
- **WHEN** generating desktop configuration
- **THEN** the system includes desktop-specific features like TUN mode, DNS settings, and process sniffing
- **AND** the system excludes mobile-specific features that are not applicable

### Requirement: Mobile platform configuration generation
The system SHALL generate optimized configuration files for mobile platforms.

#### Scenario: Mobile configuration generation
- **WHEN** the system generates configuration for mobile platforms
- **THEN** the system uses mobile-specific optimizations and settings
- **AND** the system outputs the configuration to `config_mobile.yaml`

#### Scenario: Mobile-specific features
- **WHEN** generating mobile configuration
- **THEN** the system includes mobile-specific features like battery optimization and cellular network handling
- **AND** the system excludes desktop-specific features that are not applicable

### Requirement: Magisk platform configuration generation
The system SHALL generate optimized configuration files for Magisk platform.

#### Scenario: Magisk configuration generation
- **WHEN** the system generates configuration for Magisk platform
- **THEN** the system uses Magisk-specific optimizations and settings
- **AND** the system outputs the configuration to `config_magisk.yaml`

#### Scenario: Magisk-specific features
- **WHEN** generating Magisk configuration
- **THEN** the system includes Magisk-specific integration settings
- **AND** the system excludes features that conflict with Magisk environment

### Requirement: Template-based configuration generation
The system SHALL use template-based approach to generate configuration files for different platforms.

#### Scenario: Template variable substitution
- **WHEN** the system processes configuration templates
- **THEN** the system substitutes template variables with actual node and configuration data
- **AND** the system maintains template structure and formatting

#### Scenario: Platform-specific templates
- **WHEN** the system has platform-specific templates
- **THEN** the system uses the appropriate template for each platform
- **AND** the system applies platform-specific variable substitutions

### Requirement: Multi-platform concurrent generation
The system SHALL generate configurations for multiple platforms concurrently to optimize performance.

#### Scenario: Concurrent platform generation
- **WHEN** the system generates configurations for multiple platforms
- **THEN** the system processes platform configurations concurrently
- **AND** the system ensures each platform configuration is generated correctly

#### Scenario: Shared node data
- **WHEN** generating configurations for multiple platforms
- **THEN** the system uses shared node verification and quality data
- **AND** the system applies platform-specific transformations independently

### Requirement: Configuration validation
The system SHALL validate generated configuration files for each platform.

#### Scenario: YAML syntax validation
- **WHEN** the system generates configuration files
- **THEN** the system validates YAML syntax for each output file
- **AND** the system reports any syntax errors before publication

#### Scenario: Platform-specific validation
- **WHEN** the system generates platform-specific configurations
- **THEN** the system validates platform-specific requirements and constraints
```

Full source: openspec/changes/deputy-refactor-with-toml-config/specs/multi-platform-config/spec.md

## openspec/changes/deputy-refactor-with-toml-config/specs/node-verification/spec.md

- Source: openspec/changes/deputy-refactor-with-toml-config/specs/node-verification/spec.md
- Lines: 1-110
- SHA256: 5b4c183bdbfc929893babe8fca5950ab82be829ef5d327108b628ac75cb0501e

[TRUNCATED]

```md
# Node Verification

## ADDED Requirements

### Requirement: TCP connectivity probing
The system SHALL perform TCP connectivity probing to verify node server and port accessibility.

#### Scenario: Successful TCP connection
- **WHEN** a node's server and port are accessible via TCP
- **THEN** the system marks the node as alive
- **AND** the system records the connection time

#### Scenario: Failed TCP connection
- **WHEN** a node's server and port are not accessible via TCP
- **THEN** the system marks the node as dead
- **AND** the system records the failure reason (timeout, connection refused, etc.)

#### Scenario: Missing endpoint information
- **WHEN** a node configuration lacks server or port information
- **THEN** the system marks the node as dead with reason "missing-endpoint"
- **AND** the system skips further verification for that node

### Requirement: HTTP health checking
The system SHALL perform HTTP health checking to verify node functionality.

#### Scenario: Successful HTTP health check
- **WHEN** a node successfully responds to HTTP health check requests
- **THEN** the system marks the node as healthy
- **AND** the system records the response time

#### Scenario: Failed HTTP health check
- **WHEN** a node fails to respond to HTTP health check requests
- **THEN** the system marks the node as unhealthy
- **AND** the system records the failure reason

#### Scenario: HTTP health check timeout
- **WHEN** HTTP health check exceeds the configured timeout
- **THEN** the system marks the node as unhealthy with reason "timeout"
- **AND** the system continues with other nodes

### Requirement: Latency testing and sorting
The system SHALL measure node latency and sort nodes by latency for optimal user experience.

#### Scenario: Latency measurement
- **WHEN** the system performs latency testing on a node
- **THEN** the system records the round-trip time in milliseconds
- **AND** the system performs multiple measurements for accuracy

#### Scenario: Node sorting by latency
- **WHEN** the system completes latency testing on all nodes
- **THEN** the system sorts nodes by latency in ascending order
- **AND** the system provides the sorted list for configuration generation

#### Scenario: Failed latency measurement
- **WHEN** latency measurement fails for a node
- **THEN** the system assigns a maximum latency value
- **AND** the system places the node at the end of the sorted list

### Requirement: Concurrent verification processing
The system SHALL perform node verification concurrently to optimize processing time.

#### Scenario: Concurrent TCP probing
- **WHEN** the system performs TCP connectivity probing on multiple nodes
- **THEN** the system processes nodes concurrently up to the configured limit
- **AND** the system respects the concurrency limit to avoid resource exhaustion

#### Scenario: Concurrent HTTP health checks
- **WHEN** the system performs HTTP health checks on multiple nodes
- **THEN** the system processes health checks concurrently
- **AND** the system properly handles concurrent failures and successes

#### Scenario: Resource management
- **WHEN** concurrent verification approaches resource limits
- **THEN** the system implements backpressure or queueing
- **AND** the system maintains stability without overwhelming system resources

### Requirement: Verification result aggregation
The system SHALL aggregate verification results from multiple checks into a comprehensive node status.

#### Scenario: All verifications pass
```

Full source: openspec/changes/deputy-refactor-with-toml-config/specs/node-verification/spec.md

## openspec/changes/deputy-refactor-with-toml-config/specs/quality-metrics/spec.md

- Source: openspec/changes/deputy-refactor-with-toml-config/specs/quality-metrics/spec.md
- Lines: 1-126
- SHA256: 50036c52e1a798d514f848b0e54f80a7ae2c95ca6728ee857b46f80937a2ce3d

[TRUNCATED]

```md
# Quality Metrics

## ADDED Requirements

### Requirement: Node survival rate calculation
The system SHALL calculate and report node survival rates.

#### Scenario: Overall survival rate
- **WHEN** the system completes node verification
- **THEN** the system calculates the percentage of nodes that passed verification
- **AND** the system reports the survival rate in the final statistics

#### Scenario: Per-source survival rate
- **WHEN** the system processes nodes from multiple sources
- **THEN** the system calculates survival rate for each source independently
- **AND** the system reports source-specific survival rates

### Requirement: Regional distribution analysis
The system SHALL analyze and report regional distribution of nodes.

#### Scenario: Regional node counting
- **WHEN** the system processes verified nodes
- **THEN** the system categorizes nodes by geographic region
- **AND** the system reports node count per region

#### Scenario: Regional survival analysis
- **WHEN** the system completes node verification
- **THEN** the system reports survival rate by region
- **AND** the system identifies regions with high or low node quality

### Requirement: Latency statistics generation
The system SHALL generate comprehensive latency statistics for verified nodes.

#### Scenario: Average latency calculation
- **WHEN** the system completes latency testing
- **THEN** the system calculates average latency across all verified nodes
- **AND** the system reports average latency in milliseconds

#### Scenario: Latency distribution
- **WHEN** the system has latency data for multiple nodes
- **THEN** the system generates latency distribution data
- **AND** the system reports percentiles (25th, 50th, 75th, 95th)

#### Scenario: Extremes identification
- **WHEN** analyzing latency data
- **THEN** the system identifies fastest and slowest nodes
- **AND** the system reports extreme values with node identifiers

### Requirement: Node quality scoring
The system SHALL calculate quality scores for individual nodes.

#### Scenario: Quality score calculation
- **WHEN** the system evaluates a node
- **THEN** the system calculates a quality score based on verification results
- **AND** the system considers TCP connectivity, HTTP health, and latency

#### Scenario: Quality score categories
- **WHEN** the system calculates quality scores
- **THEN** the system categorizes nodes into quality tiers (excellent, good, fair, poor)
- **AND** the system reports quality distribution

### Requirement: Change tracking and reporting
The system SHALL track and report changes between verification runs.

#### Scenario: New nodes identification
- **WHEN** comparing current verification results with previous run
- **THEN** the system identifies newly added nodes
- **AND** the system reports count and details of new nodes

#### Scenario: Failed nodes identification
- **WHEN** comparing current verification results with previous run
- **THEN** the system identifies nodes that failed verification
- **AND** the system reports count and failure reasons for failed nodes

#### Scenario: Node performance changes
- **WHEN** comparing latency data between runs
- **THEN** the system identifies significant performance changes
- **AND** the system reports nodes with improved or degraded performance

### Requirement: Statistics formatting and output
```

Full source: openspec/changes/deputy-refactor-with-toml-config/specs/quality-metrics/spec.md

## openspec/changes/deputy-refactor-with-toml-config/specs/toml-node-config/spec.md

- Source: openspec/changes/deputy-refactor-with-toml-config/specs/toml-node-config/spec.md
- Lines: 1-83
- SHA256: adbb71746ba51ce09c9bef9c07b9c39c00bd100252e320addff7661c619d24a4

[TRUNCATED]

```md
# TOML Node Configuration

## ADDED Requirements

### Requirement: Parse TOML configuration file
The system SHALL parse a TOML configuration file that contains both static nodes and subscription sources.

#### Scenario: Valid TOML configuration file
- **WHEN** the system reads a valid `nodes.toml` file
- **THEN** the system successfully parses static nodes and subscription sources
- **AND** the system extracts all configuration parameters

#### Scenario: Invalid TOML syntax
- **WHEN** the TOML file contains syntax errors
- **THEN** the system reports a clear error message indicating the line and position of the error
- **AND** the system terminates with a non-zero exit code

### Requirement: Support static node configuration
The system SHALL support static node configuration in TOML format for various proxy types.

#### Scenario: VMess static node
- **WHEN** the TOML file contains a VMess static node configuration
- **THEN** the system correctly parses the node including server, port, UUID, cipher, and other required fields
- **AND** the system validates all required fields are present

#### Scenario: Shadowsocks static node
- **WHEN** the TOML file contains a Shadowsocks static node configuration
- **THEN** the system correctly parses the node including server, port, password, and cipher
- **AND** the system validates all required fields are present

#### Scenario: Missing required fields
- **WHEN** a static node configuration is missing required fields
- **THEN** the system reports which fields are missing
- **AND** the system skips that node with a warning message

### Requirement: Support subscription source configuration
The system SHALL support subscription source configuration with URL and optional metadata.

#### Scenario: Single subscription source
- **WHEN** the TOML file contains a subscription source with a valid URL
- **THEN** the system successfully fetches and parses the subscription
- **AND** the system applies any specified prefix or filters

#### Scenario: Multiple subscription sources
- **WHEN** the TOML file contains multiple subscription sources
- **THEN** the system processes each subscription source in parallel
- **AND** the system merges nodes from all sources with proper naming to avoid conflicts

#### Scenario: Invalid subscription URL
- **WHEN** a subscription source URL is invalid or unreachable
- **THEN** the system reports the error and continues processing other sources
- **AND** the system marks the failed source in the final report

### Requirement: Configuration validation
The system SHALL validate the TOML configuration structure and content before processing.

#### Scenario: Valid configuration structure
- **WHEN** the TOML configuration follows the expected structure
- **THEN** the system proceeds with node processing
- **AND** all configuration parameters are applied correctly

#### Scenario: Unknown configuration keys
- **WHEN** the TOML file contains unknown configuration keys
- **THEN** the system warns about the unknown keys
- **AND** the system continues processing with known configuration

#### Scenario: Invalid configuration values
- **WHEN** configuration values have invalid types or ranges
- **THEN** the system reports the specific validation error
- **AND** the system uses safe default values where applicable

### Requirement: Mixed static and subscription nodes
The system SHALL support mixing static nodes and subscription nodes in the same configuration.

#### Scenario: Combined configuration
- **WHEN** the TOML file contains both static nodes and subscription sources
- **THEN** the system processes static nodes and subscription nodes together
- **AND** the system merges them into a unified node list
- **AND** the system applies consistent naming and validation to all nodes

```

Full source: openspec/changes/deputy-refactor-with-toml-config/specs/toml-node-config/spec.md


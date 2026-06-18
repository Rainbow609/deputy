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
- 新增版本控制和变更追踪机制
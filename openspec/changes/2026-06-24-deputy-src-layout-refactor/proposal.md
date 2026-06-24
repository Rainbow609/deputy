## Why

`deputy` 当前采用扁平 `scripts/` 单包布局：251 行的 `sync_nodes.py` 把编排、解析、过滤、去重、传输链、发布决策、指标聚合混在一个文件里；模块边界模糊，与参考项目 `mihomo-config` 的 `src/mihomo_config/<subpkg>/` 风格差距大，难做横向对照。传输层只有 `cloudscraper` / `requests` / `curl_cffi` 三个实现，无 retry/backoff 参数；同步编排没有 `sources/` / `core/` / `probing/` / `rendering/` 子包；`quality_metrics.py` 中的 release notes 文本被埋在调用方，缺 GHA Step Summary 写入路径。

本次重构把代码改造成与 `mihomo-config` 完全同构的 `src/deputy/<subpkg>/` 布局（`core` / `transport` / `sources` / `probing` / `rendering` / `publishing` / `utils`），补齐 `mihomo-config` 的全部 6 个传输实现与指数退避，引入订阅缓存回退与 `StepSummaryBuilder`。同时**保留** deputy 独有的 `ReleasePublisher` 条件发布逻辑、`softprops/action-gh-release@v2` + `deputy-latest` 固定 tag 的工作流步骤、`[rename]` 全局/逐源覆盖、`static_nodes` / `subscription_sources` / `exclude_keywords` 段、`NodeVerifier.address_family=auto` 回退，以及 TOML 配置文件 `nodes.toml` → `sync_config.toml` 的改名（保留在根目录）。

## What Changes

- **BREAKING**: 包布局从 `scripts/` 平面重构为 `src/deputy/` 8 子包 + `scripts/sync_nodes.py` 8 行 shim
- **BREAKING**: TOML 配置文件从 `nodes.toml` 改名为 `sync_config.toml`（保留在根目录）
- **新增**: 6 个传输实现 — `MihomoTransport`（clash-meta UA）+ `CloudscraperTransport` + `RequestsTransport` + `CurlCffiTransport` + `CurlCffiSafariTransport` + `TlsClientTransport`
- **新增**: `TransportChain` 指数退避参数（`base_delay` / `max_delay` / `jitter_range` / `max_attempts_per_transport` / `max_total_attempts`）
- **新增**: `[subscription.fetch]` TOML 段，配置传输链退避参数（与 mihomo-config 对齐）
- **新增**: 订阅缓存回退机制 `subscriptions/<source>.yaml`，临时错误自动回退
- **新增**: `StepSummaryBuilder` 写入 `$GITHUB_STEP_SUMMARY`，含订阅源状态表、地区分布表、节点统计
- **新增**: `mihomo-config` 风格的 `core/nodes.py::MergeResult` / `merge_proxy_sets` / `valid_proxies` 合并 + 验证助手
- **新增**: `tls-client` 依赖（用于 `TlsClientTransport`）
- **保持**: `ReleasePublisher` 全部语义（条件发布、`_NoopAPI`、`make_version_tag`）
- **保持**: GitHub Releases 发布流程（`softprops/action-gh-release@v2` + `deputy-latest` tag + `hashFiles` 守卫）
- **保持**: `[rename]` 全局/逐源覆盖 + `static_nodes` / `subscription_sources` / `exclude_keywords` 段

## Capabilities

### New Capabilities

- `deputy-src-layout`: 与 mihomo-config 完全同构的 `src/deputy/<subpkg>/` 8 子包布局
- `transport-backoff`: `TransportChain` 指数退避参数 + 6 个传输实现
- `subscription-cache-fallback`: 订阅缓存回退机制（`subscriptions/*.yaml` + 临时错误判定）
- `gha-step-summary`: `StepSummaryBuilder` GHA Step Summary 写入路径

### Modified Capabilities

- `toml-node-config`: 配置文件名 `nodes.toml` → `sync_config.toml`（保留在根目录）；新增 `[subscription.fetch]` 段
- `github-releases-distribution`: workflow `run:` 路径更新为 `scripts/sync_nodes.py`，`push.paths` 改为 `src/deputy/**`
- `node-verification`: `NodeVerifier` 保留为薄包装，新代码统一走 `tcp_check` / `tcp_probe`
- `quality-metrics`: `format_release_notes` 改名为 `build_release_notes` 迁入 `utils/summary.py`

## Impact

**代码影响**:
- `pyproject.toml` 从 hatchling 切换到 setuptools + src 布局（PEP 517 标准）
- `.github/workflows/sync-and-release.yml` 的 `run:` 命令和 `push.paths` 更新
- `scripts/sync_nodes.py` 从 251 行替换为 8 行 shim
- 9 个测试文件按模块拆分，新增 ~50 用例（108 → 150）

**用户影响**:
- 配置文件名变更 `nodes.toml` → `sync_config.toml`，本地运行命令需更新
- 包导入路径变更 `scripts.fetch_transport` → `deputy.transport.chain` 等
- 工作流推送路径触发条件变更（`src/deputy/**` 触发 workflow）
- 所有现有用户功能保持不变：节点拉取、TCP 探活、模板渲染、GitHub Releases 发布

**部署影响**:
- 依赖新增 `tls-client>=1.0,<2`
- GHA workflow 需在 PR 合并后下一次 cron 自动跑通；`config.yaml` 资产会出现在 `deputy-latest` tag 下

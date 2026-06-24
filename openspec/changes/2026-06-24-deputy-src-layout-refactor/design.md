## Context

`/Users/liangzongyou/git/deputy` 当前采用扁平的 `scripts/` 单包布局，251 行的 `sync_nodes.py` 把编排、解析、过滤、去重、传输链、发布决策、指标聚合混在一个文件里；模块边界模糊，与参考项目 `/Users/liangzongyou/git/mihomo-config` 的 `src/mihomo_config/<subpkg>/` 风格差距大，难做横向对照。传输层只有 cloudscraper/requests/curl_cffi 三种实现，无 retry/backoff 参数；同步编排没有 `sources/`/`core/`/`probing/`/`rendering/` 子包；`quality_metrics.py` 中的 release notes 文本被埋在调用方，缺 GHA Step Summary 写入路径。

本次重构把代码改造成与 mihomo-config 完全同构的 `src/deputy/<subpkg>/` 布局（`core`、`transport`、`transport/impls`、`sources`、`probing`、`rendering`、`publishing`、`utils`），补齐 mihomo-config 的全部 6 个传输实现与指数退避，引入订阅缓存回退与 `StepSummaryBuilder`。同时**保留** deputy 独有的 `ReleasePublisher` 条件发布逻辑、`softprops/action-gh-release@v2` + `deputy-latest` 固定 tag 的工作流步骤、`[rename]` 全局/逐源覆盖、`static_nodes`/`subscription_sources`/`exclude_keywords` 段、`NodeVerifier.address_family=auto` 回退，以及 TOML 配置文件 `nodes.toml` → `sync_config.toml` 的改名（保留在根目录）。

## Goals / Non-Goals

**Goals:**
- 包布局与 mihomo-config 完全同构，便于后续 back-port 与横向对照
- 补齐 6 个传输实现（Mihomo + Cloudscraper + Requests + CurlCffi + CurlCffiSafari + TlsClient）+ 指数退避
- 引入订阅缓存回退（`subscriptions/*.yaml` + 临时错误判定）
- 引入 GHA Step Summary 写入路径
- 保持 `ReleasePublisher` 全部语义与 GitHub Releases 发布流程
- 保持 `[rename]` 全局/逐源、`static_nodes`、`subscription_sources`、`exclude_keywords` 段
- 把测试按模块拆分，新增 coverage 至 150 用例

**Non-Goals:**
- 不引入 mihomo-config 的 Gist / config-output 分支发布模式（保持单 Releases 模式）
- 不使用 `SUB_URLS` 环境变量发现订阅源（继续用 `[subscription_sources]` TOML 静态声明）
- 不重构节点名清洗算法（保持现有 5 步规则）
- 不重写 `ReleasePublisher` 发布契约（保持条件发布 / `_NoopAPI`）
- 不变更 `deputy-latest` 固定 tag（保持 `softprops/action-gh-release@v2` 调用契约）

## Decisions

### 1. 包布局选 `src/deputy/` + 8 子包

**理由**: PEP 517 标准实践 + 与 mihomo-config 完全对齐便于后续 back-port。`src/` 布局让测试隔离更可靠，避免 `scripts/__init__.py` 这种半包半目录的歧义。

**替代方案**: 保持 `scripts/` 平面布局但分更多子目录。**否决理由**: 仍然不是 PEP 517 标准实践，且与 mihomo-config 风格差距依旧。

### 2. 构建后端 hatchling → setuptools

**理由**: mihomo-config 用 setuptools，对 `src/` 布局支持稳定（`package-dir = {"" = "src"}` 一行配置）；hatchling 在 `packages = ["scripts"]` 写法下迁移成本反而更高（需重写 `[tool.hatch.build.targets.wheel]`）。

**替代方案**: 保持 hatchling，配置 `packages = ["src/deputy"]`。**否决理由**: 与 mihomo-config 配置惯例不一致，未来 back-port 需要额外迁移步骤。

### 3. 传输实现位置选 `transport/impls/*.py`（6 文件）

**理由**: 与 mihomo-config 完全同构（mihomo-config 同样 6 文件：cloudscraper/requests/curl_cffi/curl_cffi_safari/mihomo/tls_client），便于按需替换实现；每文件 ~30-50 行，可读性更好。

**替代方案**: 单 `chain.py` 含 6 类。**否决理由**: 文件过长（预计 400+ 行），职责混乱，难单测。

### 4. `NodeVerifier` 保留为薄包装

**理由**: E2E 测试已有 3 处 `patch("scripts.node_verifier.socket.socket")` 风格 mock；保留包装可平滑迁移至新 `deputy.probing.tcp.socket.socket` 路径。新代码统一走 `tcp_check` / `tcp_probe`。

**替代方案**: 直接删除 `NodeVerifier`。**否决理由**: 现有 E2E 测试与 helper 脚本会全部失效，迁移成本高。

### 5. `format_release_notes` 改名为 `build_release_notes` 迁入 `utils/summary.py`

**理由**: 释放 release body 文本与 GHA Step Summary 的命名空间，避免 `format_release_notes` 与 `StepSummaryBuilder` 互相误用。

**替代方案**: 留在 `utils/quality.py`。**否决理由**: quality 模块应该只关心纯计算指标（survival_rate / latency），不应包含文档生成。

### 6. 缓存策略选 `subscriptions/`（项目根）

**理由**: 与 mihomo-config 行为一致（同样的相对路径）。缺点是需 `.gitignore` 跟进。

**替代方案**: 仓库外 / `.cache/`。**否决理由**: 与 mihomo-config 行为不一致，跨项目对比时增加认知负担。

### 7. 配置文件名 `nodes.toml` → `sync_config.toml`（保留根）

**理由**: 用户决策（不迁到 `config/`）+ 命名与 mihomo-config 对齐（mihomo-config 用 `config/sync_config.toml`，deputy 用 `sync_config.toml`）。

**替代方案**: 迁到 `config/` 目录。**否决理由**: 用户决策不迁；保持现有目录结构对老用户友好。

### 8. TOML 新段 `[subscription.fetch]`（5 字段）

**理由**: 解锁 mihomo-config 的指数退避能力；默认值取 mihomo-config 生产值（`base_delay=0.5`、`max_delay=8.0`、`jitter_range=0.3`、`max_attempts_per_transport=4`、`max_total_attempts=20`、`timeout=45`）。

**替代方案**: 不引入，沿用 3 传输链。**否决理由**: 放弃 mihomo-config 的核心能力。

### 9. GHA workflow 仅更新 `run:` + `push.paths`，保留 Releases 单模式

**理由**: 用户决策（不引入 Gist / config-output）。

**替代方案**: 引入 Gist / config-output 双发布。**否决理由**: 用户决策，且 mihomo-config 的 Gist 模式有第三方平台依赖。

### 10. 测试拆分粒度 1 文件 → 1 文件/模块（14 文件）

**理由**: 与 mihomo-config 风格一致，便于定位失败；现有 75 个用例断言全部保留，只调整 `import` 路径。

**替代方案**: 保留 1 个大 `test_sync_nodes.py`。**否决理由**: 与 mihomo-config 风格不一致，难以快速定位失败用例。

### 11. 节点名清洗规则保持现有 5 步（不加 `MB/KB/GB/s` 剥离）

**理由**: 避免改变 deputy 当前输出行为；列为 follow-up change。

**替代方案**: 加入 mihomo-config 的流速剥离。**否决理由**: 改变输出会导致现有用户的 `config.yaml` 出现非预期 diff，影响 Release 资产。

## Risks / Trade-offs

### 主要风险

1. **patch 路径漂移**：`patch("scripts.node_verifier.socket.socket")` 风格 mock 有 3 处需改为 `patch("deputy.probing.tcp.socket.socket")`；缓解：迁移前 `grep -r "scripts\." tests/` 一次性列出按表替换。

2. **新传输实现依赖不可用**：`tls-client` 与新版 `curl-cffi` 在某些 CI 环境安装慢；缓解：`importlib.util.find_spec` + `available: bool` + `TransportChain` 自动跳过 `available=False` 的 transport。

3. **`subscriptions/` 缓存目录膨胀**：不 `.gitignore` 会污染仓库；缓解：在 `.gitignore` 追加 `subscriptions/*.yaml`。

4. **GHA workflow 路径遗漏**：`push.paths` 若遗漏 `src/deputy/**`，后续修改不会触发 workflow；缓解：M 步骤末尾用 `actionlint` 或 Python YAML 解析静态校验。

5. **`SUB_URLS` vs `subscription_sources` 语义混淆**：mihomo-config 用环境变量，deputy 用 TOML 静态声明；缓解：在 `core/sync.py` 顶部注释明确 `load_config(sync_config.toml).subscription_sources` 是唯一来源。

6. **缓存回退改变"全失败拒发"语义**：引入缓存后单源失败可能因缓存回退变 0 节点；缓解：core/sync.py 区分两种错误信息——缓存命中但 0 节点 → "zero alive nodes after fetch+cache fallback"；全失败 → 保留 "all subscription sources failed"。

7. **`pyproject.toml` 切换 hatchling → setuptools 误重复段**：手动 Write 时偶发 `Cannot declare ('project',) twice` 错误；缓解：用 SearchReplace 校验现有内容后再 Write。

### Trade-offs

- **配置文件名变更成本**：所有现有用户的 `nodes.toml` 需改为 `sync_config.toml`，命令调用需更新。**缓解**: 文档更新 + README 链接明确指向新文件名。
- **`src/` 布局相对路径依赖**：本地 `python scripts/sync_nodes.py` 运行需 `src/` 在 sys.path 中；shim 自动处理（`scripts/sync_nodes.py` 第 7 行把 `src/` 加进 sys.path）。
- **测试 mock 复杂度提升**：需要 mock 6 个 transport 而非 3 个；**缓解**: `importlib.util.find_spec` 提供 `available` 标志，链自动跳过未安装的 transport。

## Migration Plan

1. **Pre-flight**: 创建 `pre-src-refactor` tag + `refactor/src-layout` 分支（步骤 A）。
2. **Implementation**: 按 A-Q 17 步顺序执行（步骤 B-Q），每步完成后用 `pytest tests/<module>` 验证。
3. **Validation**: 全量 `pytest tests/ -v` 验证 150 用例全绿（步骤 Q）。
4. **Documentation**: 更新 README.md（步骤 O）+ docs/nodes-toml-guide.md（最小修改）。
5. **PR & Squash**: 创建 PR 从 `refactor/src-layout` → `main`，CI 跑通后 squash merge。
6. **Tag retention**: 保留 `pre-src-refactor` tag 60 天以便回滚。

## Open Questions

- 是否要把 `subscriptions/` 加进 `.gitignore`？（已在 L 步骤加入 `subscriptions/*.yaml`）
- 是否要在 `deputy.utils.summary` 里加 `region_stats` 区域分布表？（已加入，通过 `region_counts()`）
- 是否要在 `core/sync.py` 加 `--dry-run` 跳过发布步骤？（可作 follow-up change）

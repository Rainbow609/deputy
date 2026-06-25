# Deputy src-layout refactor — Tasks

## A. 准备：备份与依赖

- [x] A.1 `git tag pre-src-refactor` 创建回滚锚点
- [x] A.2 `git checkout -b refactor/src-layout` 创建开发分支

## B. 创建 src/deputy/ 包骨架

- [x] B.1 创建 9 个空 `__init__.py`（根 + core/transport/transport/impls/sources/probing/rendering/publishing/utils）

## C. 迁移 transport 模块（chain + 5 impls）

- [x] C.1 `src/deputy/transport/chain.py` — `TransportChain` 升级支持 `base_delay`/`max_delay`/`jitter_range`/`max_attempts_per_transport`/`max_total_attempts`/Cloudflare challenge 检测；保留 `max_attempts` 关键字兼容
- [x] C.2 `src/deputy/transport/impls/cloudscraper.py` — `CloudscraperTransport` 兼容 `create_scraper`/`create_cloudScraper` 双 API
- [x] C.3 `src/deputy/transport/impls/requests.py` — `RequestsTransport` 默认 UA Chrome 126
- [x] C.4 `src/deputy/transport/impls/curl_cffi.py` — `CurlCffiTransport` + `CurlCffiSafariTransport`，`importlib.util.find_spec` 可选依赖探测
- [x] C.5 `src/deputy/transport/impls/mihomo.py` — `MihomoTransport` UA `clash-meta`，自动剥离 `flag=clash`
- [x] C.6 `src/deputy/transport/impls/tls_client.py` — `TlsClientTransport` 懒加载 tls-client

## D. 迁移 sources 模块

- [x] D.1 `src/deputy/sources/config.py` — 保留 `DeputyConfig`/`SubscriptionConfig`/`ProbeConfig`/`load_config`/`_validate_rename_table`；新增 `FetchConfig` + `write_text_atomic`
- [x] D.2 `src/deputy/sources/subscription.py` — `SubscriptionFetchResult`、`cache_path`/`load_subscription_cache`/`save_subscription_cache`/`prune_subscription_caches`、`load_clash_subscription_yaml` 去 ANSI、`add_clash_flag`、`default_transports()` (6 个 transport)、`fetch_clash_subscription`/`fetch_subscription_with_cache` 缓存回退

## E. 迁移 probing 模块

- [x] E.1 `src/deputy/probing/tcp.py` — 保留 `classify_failure`/`resolve_addresses`/`_family_value`；新增 `ProbeResult`/`tcp_check`/`tcp_probe`；保留 `NodeVerifier` 兼容包装

## F. 迁移 rendering 模块

- [x] F.1 `src/deputy/rendering/config.py` — 保留 `_safe_format_map`/`_quote_if_needed`/`generate_proxy_items_yaml`/`render_template`；新增 `generate_proxies_yaml`/`yaml_dump`

## G. 迁移 utils 模块

- [x] G.1 `src/deputy/utils/logging.py` — 保留 `GhaLogger`/`LogLevel`；新增 `is_ci`/`warning`/`error`/`notice`/`debug`/`group`/`endgroup`/`set_output`/`set_env`/`add_mask`/`write_summary`/`utc_now_iso`/`StepSummaryBuilder`
- [x] G.2 `src/deputy/utils/quality.py` — 保留 `compute_survival_rate`/`compute_latency_stats`/`_percentile`
- [x] G.3 `src/deputy/utils/summary.py` — 新增 `build_release_notes`/`build_probe_json_payload`/`fetch_status_rows`/`region_counts`/`print_latency_overview`/`print_ci_probe_json`

## H. 迁移 publishing 模块（保留 ReleasePublisher）

- [x] H.1 `src/deputy/publishing/release.py` — 完整保留 `make_version_tag`/`ReleaseAPI`/`_NoopAPI`/`ReleasePublisher`/`ReleasePublisher.default`/`publish`

## I. 迁移 core 模块

- [x] I.1 `src/deputy/core/nodes.py` — 合并 `sanitize_node_name`/`RenameConfig`/`build_rename_config`/`apply_node_rename` + 新增 `valid_proxies`/`filter_proxies`/`deduplicate_proxies`/`proxy_names`/`compute_dialer_names`/`group_by_source`/`MergeResult`/`merge_proxy_sets`
- [x] I.2 `src/deputy/core/sync.py` — 新版 `run_sync` 编排：`load_config` → `fetch_subscription_with_cache` → `tcp_probe` → `render_template` → `ReleasePublisher` + `StepSummaryBuilder` GHA Summary + `print_ci_probe_json`

## J. 重写 scripts/sync_nodes.py 为 shim

- [x] J.1 `scripts/sync_nodes.py` — 10 行 shim，把 `src/` 加进 sys.path 并委托 `deputy.core.sync.main()`

## K. 更新 pyproject.toml

- [x] K.1 hatchling → setuptools + src 布局
- [x] K.2 依赖新增 `tls-client>=1.0,<2`

## L. nodes.toml → sync_config.toml 改名

- [x] L.1 `git mv nodes.toml sync_config.toml`
- [x] L.2 新增 `[subscription.fetch]` 段
- [x] L.3 同步更新 `docs/nodes-toml-guide.md`
- [x] L.4 `.gitignore` 追加 `subscriptions/*.yaml`

## M. 更新 sync-and-release.yml workflow

- [x] M.1 `push.paths` 更新为 `src/deputy/**` + `scripts/sync_nodes.py` + `sync_config.toml`
- [x] M.2 `Run sync` step 的 `run:` 改为 `uv run python scripts/sync_nodes.py --config sync_config.toml ...`
- [x] M.3 `concurrency` 块添加（避免长时间排队）
- [x] M.4 保留 `softprops/action-gh-release@v2` + `deputy-latest` + `hashFiles` 守卫

## N. 迁移并扩展测试（按模块拆分）

- [x] N.1 `tests/conftest.py` — 把 `src/` 加入 sys.path 一次
- [x] N.2 `tests/fixtures/test_subscription.yaml` — 跨模块 fixture
- [x] N.3 `tests/test_transport_chain.py` — 10 个用例
- [x] N.4 `tests/test_transport_impls.py` — 13 个用例（6 transport + 边界）
- [x] N.5 `tests/test_toml_config.py` — 11 个用例
- [x] N.6 `tests/test_subscription_sources.py` — 14 个用例（缓存/ANSI strip/flag-clash）
- [x] N.7 `tests/test_probing_tcp.py` — 11 个用例
- [x] N.8 `tests/test_rendering_config.py` — 12 个用例
- [x] N.9 `tests/test_quality_metrics.py` — 9 个用例
- [x] N.10 `tests/test_logging.py` — 8 个用例（含 `StepSummaryBuilder`）
- [x] N.11 `tests/test_publishing_release.py` — 5 个用例
- [x] N.12 `tests/test_core_nodes.py` — 27 个用例（sanitize/rename/filter/dedup/merge）
- [x] N.13 `tests/test_sync_orchestration.py` — 3 个用例
- [x] N.14 `tests/test_sync_summary.py` — 6 个用例
- [x] N.15 `tests/test_sync_nodes_workflow.py` — 7 个用例（workflow YAML 结构断言）
- [x] N.16 `tests/test_e2e_smoke.py` — 4 个 E2E 用例（patch 路径迁移到 `deputy.*`）

## O. 更新 README.md

- [x] O.1 章节重写：特性 + 包结构 + 快速开始 + 配置 + 传输链 + CI/CD + 开发
- [x] O.2 添加新文档链接 `openspec/changes/2026-06-24-deputy-src-layout-refactor/`

## P. 清理旧 scripts/*.py

- [x] P.1 删除 8 个已迁移的 `scripts/*.py` 文件 + `scripts/__pycache__/`
- [x] P.2 保留 `scripts/sync_nodes.py` 为 shim

## Q. 端到端验证

- [x] Q.1 `python -c "import yaml; yaml.safe_load(...)"` workflow YAML 解析无错
- [x] Q.2 `PYTHONPATH=src .venv/bin/pytest tests/ -q` 全 150 用例通过
- [x] Q.3 `python -c "import deputy.core.sync; ..."` 模块导入 OK
- [x] Q.4 workflow 静态校验（`actionlint` 若可用；Python YAML 解析已通过）

## R. 新增 openspec change 记录

- [x] R.1 `.openspec.yaml` schema spec-driven
- [x] R.2 `.comet.yaml` workflow 配置
- [x] R.3 `proposal.md` Why / What Changes / Capabilities / Impact
- [x] R.4 `design.md` Context / Goals / Non-Goals / Decisions / Risks / Migration / Open Questions
- [x] R.5 `tasks.md` 对应 A-Q 17 步，每步用 `- [x]` 标记完成

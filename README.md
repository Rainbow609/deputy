# deputy

多源 Clash Meta 配置生成器，结构与 [`mihomo-config`](https://github.com/.../mihomo-config) 同构。

> 感谢 [`anaer/Sub`](https://github.com/anaer/Sub) 项目提供的优质订阅源整理。
>
> **订阅地址**: `https://gh-proxy.org/https://github.com/Rainbow609/deputy/releases/download/deputy-latest/config.yaml`

每 3 小时自动从多个订阅源拉取节点、TCP 探活过滤、按模板渲染 `config.yaml`，并在配置变更时发布到 GitHub Releases。

## 特性

- **`src/` 包布局** — 8 个子包（`core` / `transport` / `sources` / `probing` / `rendering` / `publishing` / `utils`），与 mihomo-config 完全同构。
- **6 个传输实现 + 指数退避** — `cloudscraper` → `requests` → `curl_cffi` → `curl_cffi_safari` → `mihomo` (clash-meta UA) → `tls_client`，每轮之间 `base_delay × 2^attempt + jitter` 退避。
- **订阅缓存回退** — `subscriptions/<source>.yaml` 暂存上次成功结果，临时错误自动回退到缓存。
- **TCP 探活 + 延迟统计** — 并发探测，支持 `address_family=auto` IPv4/IPv6 回退，输出 `avg_ms / min_ms / max_ms / variance / jitter / p50 / p95`。
- **节点名清洗** — 去 ASCII 标点 + 去 emoji/装饰符号 + 折叠空白 + 全角空格归一化。
- **TOML 配置** — `sync_config.toml`（原 `nodes.toml`）统一管理 `[subscription]` / `[subscription.fetch]` / `[probe]` / `[subscription_sources]` / `[[static_nodes]]` / `[rename]`。
- **GHA Step Summary** — `StepSummaryBuilder` 写入 `$GITHUB_STEP_SUMMARY`，含订阅源状态表、地区分布表、节点统计。
- **GitHub Releases** — 配置变更时通过 `softprops/action-gh-release@v2` 在 `deputy-latest` tag 发布 `config.yaml` 资产。

## 包结构

```
deputy/
├── src/deputy/
│   ├── core/              # 主编排 + 节点清洗/合并
│   │   ├── nodes.py       # sanitize_node_name / apply_node_rename / merge_proxy_sets / valid_proxies
│   │   └── sync.py        # run_sync() + main() 入口
│   ├── transport/         # HTTP 传输链
│   │   ├── chain.py       # TransportChain + TransportError + 退避算法
│   │   └── impls/         # 6 个具体传输实现
│   │       ├── cloudscraper.py
│   │       ├── requests.py
│   │       ├── curl_cffi.py    # Chrome + Safari fingerprint
│   │       ├── mihomo.py       # clash-meta UA
│   │       └── tls_client.py   # tls-client (utls)
│   ├── sources/           # 输入配置 + 订阅源
│   │   ├── config.py      # load_config + write_text_atomic
│   │   └── subscription.py # fetch_subscription_with_cache + 缓存/ANSI strip/flag-clash
│   ├── probing/
│   │   └── tcp.py         # tcp_check / tcp_probe / ProbeResult + NodeVerifier 兼容
│   ├── rendering/
│   │   └── config.py      # render_template + generate_proxies_yaml + yaml_dump
│   ├── publishing/
│   │   └── release.py     # ReleasePublisher + make_version_tag（保留全部语义）
│   └── utils/
│       ├── logging.py     # GhaLogger + StepSummaryBuilder + GHA workflow commands
│       ├── quality.py     # compute_survival_rate / compute_latency_stats / _percentile
│       └── summary.py     # build_release_notes / build_probe_json_payload / region_counts
├── scripts/
│   └── sync_nodes.py      # 8 行委托入口
├── sync_config.toml       # TOML 配置（原 nodes.toml）
├── config.template.yaml   # Clash 模板（含占位符）
├── tests/                 # 14 个测试文件，按模块拆分
│   ├── conftest.py
│   ├── fixtures/test_subscription.yaml
│   ├── test_transport_chain.py + test_transport_impls.py
│   ├── test_toml_config.py + test_subscription_sources.py
│   ├── test_probing_tcp.py + test_rendering_config.py
│   ├── test_quality_metrics.py + test_logging.py
│   ├── test_publishing_release.py + test_core_nodes.py
│   ├── test_sync_orchestration.py + test_pipeline_integration.py
│   ├── test_sync_summary.py + test_sync_nodes_workflow.py
│   └── test_e2e_smoke.py
└── .github/workflows/sync-and-release.yml
```

## 快速开始

```bash
# 1. 编辑 sync_config.toml，填入你的订阅源
# 2. 同步依赖并运行
uv sync --locked
uv run python scripts/sync_nodes.py \
    --config sync_config.toml \
    --template config.template.yaml \
    --output config.yaml \
    --previous config.previous.yaml
# 3. 生成的 config.yaml 即为最终配置，可导入 mihomo/Clash Meta
```

也可以直接：

```bash
uv run python -m deputy.core.sync
```

## 配置（`sync_config.toml`）

| 段 | 用途 |
|---|---|
| `[subscription]` | 格式 (`clash` / `v2ray`) + 排除关键词 |
| `[subscription.fetch]` | 传输链退避参数（`base_delay` / `max_delay` / `jitter_range` / `max_attempts_per_transport` / `max_total_attempts` / `timeout`） |
| `[probe]` | TCP 探活参数（`timeout` / `concurrency` / `retries` / `address_family`） |
| `[subscription_sources]` | `name = url` 映射 |
| `[[static_nodes]]` | 静态节点列表 |
| `[rename]` | 全局默认 + `name-keyed` 逐源覆盖（`prefix` / `sanitize` / `separator`） |

完整示例：

```toml
[subscription]
format = "clash"
exclude_keywords = ["官网", "到期", "剩余流量"]

[subscription.fetch]
base_delay = 0.5
max_delay = 8.0
jitter_range = 0.3
max_attempts_per_transport = 4
max_total_attempts = 20
timeout = 45

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[subscription_sources]
"anaer"  = "https://anaer.github.io/Sub/proxies.yaml"
"vxiaov" = "https://raw.githubusercontent.com/vxiaov/free_proxies/main/clash/clash.provider.yaml"

[rename]
sanitize = true
separator = "-"

[rename."anaer"]
prefix = "AN"
```

## 传输链 fallback 顺序

```
MihomoTransport (clash-meta UA)
  ↓ 失败
CloudscraperTransport (Cloudflare JS challenge bypass)
  ↓ 失败
RequestsTransport (Chrome 126 UA)
  ↓ 失败
CurlCffiTransport (curl_cffi impersonate="chrome120")
  ↓ 失败
CurlCffiSafariTransport (curl_cffi impersonate="safari17_0")
  ↓ 失败
TlsClientTransport (tls-client utls chrome_120)
```

`importlib.util.find_spec` 在构造时探测 `curl_cffi` / `tls_client`，未安装则 `available = False`，链自动跳过。

## CI/CD

`.github/workflows/sync-and-release.yml` 触发条件：

- `cron: "0 */3 * * *"` 每 3 小时
- `workflow_dispatch` 手动触发
- `push` 到 `main` 分支且改动以下路径：`src/deputy/**` / `scripts/sync_nodes.py` / `config.template.yaml` / `sync_config.toml` / `pyproject.toml` / `uv.lock`

发布流程：

1. 检出代码 → `uv sync --locked`
2. `uv run python scripts/sync_nodes.py` 生成 `config.yaml`
3. 保存 `config.previous.yaml` 用于下次条件发布
4. **仅当** `config.yaml` 变更时，通过 `softprops/action-gh-release@v2` 在 `deputy-latest` tag 发布 `config.yaml` 资产

订阅地址：

```
https://github.com/<user>/<repo>/releases/latest/download/config.yaml
```

并发控制：`concurrency: sync-nodes-${{ github.ref }}` + `cancel-in-progress: true`，避免长时间排队。

## 开发

```bash
# 同步依赖
uv sync --locked

# 跑测试（14 个文件，100+ 用例）
uv run pytest tests/ -v

# 按模块跑
uv run pytest tests/test_transport_chain.py tests/test_transport_impls.py
uv run pytest tests/test_core_nodes.py
uv run pytest tests/test_sync_orchestration.py tests/test_e2e_smoke.py
```

导入示例：

```python
from deputy.core.sync import run_sync
from deputy.sources.config import load_config
from deputy.publishing.release import ReleasePublisher

cfg = load_config("sync_config.toml")
summary = run_sync(
    config_path="sync_config.toml",
    template_path="config.template.yaml",
    output_config="config.yaml",
    previous_config="config.previous.yaml",
)
print(summary["version"], summary["survival_rate"])
```

## 详细文档

- 节点配置: [docs/nodes-toml-guide.md](docs/nodes-toml-guide.md)
- 技术设计: [openspec/specs/](openspec/specs/)
- 重构方案: [openspec/changes/2026-06-24-deputy-src-layout-refactor/](openspec/changes/2026-06-24-deputy-src-layout-refactor/)
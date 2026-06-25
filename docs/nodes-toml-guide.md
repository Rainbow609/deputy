# sync_config.toml 配置指南

`sync_config.toml` 是 deputy 的统一节点配置文件（原 `nodes.toml`，v0.2 起改名）。它支持两种节点来源：

1. **静态节点** — 直接写在文件里，由你维护
2. **订阅源** — 从远端 URL 拉取，自动验证

## 完整结构

```toml
[subscription]
format = "clash"
exclude_keywords = ["官网", "到期", "剩余流量"]

[probe]
timeout = 3
concurrency = 30
retries = 0
address_family = "auto"

[[static_nodes]]
name = "my-hk-1"
type = "vmess"
server = "hk1.example.com"
port = 443
uuid = "..."
alterId = 0
cipher = "auto"

[subscription_sources]
"星链云" = "https://..."
"三分" = "https://..."

[rename]
sanitize = true
separator = "-"

[rename."星链云"]
prefix = "XL"

[rename."三分"]
prefix = "SF"
```

## 字段说明

### `[subscription]`

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `format` | string | `clash` | 订阅格式，目前仅支持 `clash` |
| `exclude_keywords` | list[string] | `[]` | 节点名包含任一关键词的节点会被过滤 |

### `[probe]`

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `timeout` | int | 3 | TCP 探测超时（秒），范围 1-30 |
| `concurrency` | int | 30 | 并发探测数，范围 1-200 |
| `retries` | int | 0 | 每个地址族的额外轮次（0=只跑一轮） |
| `address_family` | string | `auto` | `auto` / `ipv4` / `ipv6` |

### `[[static_nodes]]`

每个 `[[static_nodes]]` 段代表一个静态节点。字段集对应标准 Clash 代理协议（vmess / vless / ss / trojan / hysteria 等）。

### `[subscription_sources]`

键值对表。键是订阅源名称，会作为前缀加到该源的所有节点名上；值是订阅 URL。

### `[rename]`

节点重命名配置（可选）。支持全局默认和逐源覆盖。

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `sanitize` | bool | `true` | 是否清洗节点名：去 ASCII 标点、emoji/旗帜、折叠空白 |
| `separator` | string | `"-"` | 前缀与节点名之间的分隔符 |
| `prefix` | string | 源名称 | 自定义前缀，仅在 `[rename."源名"]` 子段中可用 |

**逐源覆盖**：在 `[rename."源名"]` 子段中设置的值会覆盖全局默认。例如：

```toml
[rename]
sanitize = true       # 全局默认清洗
separator = "-"        # 全局默认分隔符

[rename."anaer"]
prefix = "AN"          # anaer 源使用 AN 前缀而非源名

[rename."vxiaov"]
prefix = "VX"
sanitize = false       # vxiaov 源禁用清洗
```

**清洗规则**（当 `sanitize = true`）：

1. 去除 ASCII 标点：`|()[]{}<>!@#$%^&*=+`~?`
2. 去除 emoji/装饰符号（Unicode So/Sm 类别）
3. 全角空格 U+3000 → 半角空格
4. 连续空白折叠为单个空格
5. 去除首尾空白

清洗后节点名为空的节点会被自动丢弃。静态节点（`[[static_nodes]]`）不受重命名影响。
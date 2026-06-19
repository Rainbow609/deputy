## Why

仓库当前同时运行两条配置生成管线：老 `get_node_list.py`（每 30 分钟从订阅源下载 clash yaml，commit 到 main）和新 `sync_nodes.py`（每 3 小时从 `nodes.toml` 渲染 `config.yaml` 发布到 GitHub Release）。老管线产生的 5 个 nite07 订阅源被风控/失效后返回 `{}` 空响应，CI 静默吞掉，main 分支被持续污染。老管线的 4 个平台输出（desktop/mobile/mobile_baipiao/magisk）已无下游消费者，新管线（单 `config.yaml`）才是官方方向。退役老管线，消除噪音源，统一仓库到单管线。

## What Changes

- **BREAKING** 删除 `get_node_list.py`（老管线主脚本）
- **BREAKING** 删除 `proxy_providers/` 整个目录（11 个 yaml，5 个是 3 字节 `{}`）
- **BREAKING** 删除 `rule_providers/` 整个目录（14 个 yaml；这些是老管线缓存产物，新管线使用 `config.template.yaml` 中的 http rule-providers 由客户端自行拉取）
- **BREAKING** 删除 4 个老输出配置：`clash_config_v3.yaml`、`config_mobile.yaml`、`config_mobile_baipiao.yaml`、`config_magisk.yaml`
- **BREAKING** 删除 `.github/workflows/schedule-get-node-list.yml`（老管线触发器，每 30 min 跑）
- **BREAKING** 删除 `templates/` 全部 6 个 yaml（`head.yaml`、`head_mobile.yaml`、`proxy-providers.yaml`、`proxy-providers_baipiao.yaml`、`rules_group.yaml`、`rules_group_mobile.yaml`）
- 修改 `config.template.yaml` 第 15/23/31 行的 `path: ./rule_provider/...` → `./rule_providers/...`（单复数 typo，顺手修；路径仍作为 Clash/mihomo 客户端的本地规则缓存路径存在）
- 修改 `openspec/specs/multi-platform-config/spec.md` 删除 Desktop / Mobile / Magisk / Multi-platform concurrent 四个 requirement，新增 Single pipeline generation requirement，并将剩余模板、校验、输出 requirement 收敛为单一 `config.yaml` 管线语义

## Capabilities

### New Capabilities
（无新增 capability — 本 change 是减法）

### Modified Capabilities
- `multi-platform-config`: 删除多平台输出与并发生成要求；新增单管线生成要求；保留并改写为单一 `config.yaml` 的模板生成、校验、输出管理要求

## Impact

- **CI/Workflow**: `.github/workflows/sync-and-release.yml` 继续运行（无变更），但 `schedule-get-node-list.yml` 删除后 main 分支不再被老管线定时 commit
- **下游用户**: 仅当用户直接消费 `clash_config_v3.yaml` / `config_mobile.yaml` / `config_magisk.yaml` 文件时才受影响 — 这些文件应已无人使用，因为新管线发布的 `config.yaml` 在 GitHub Release `deputy-latest`
- **main 分支体积**: 减少 11 + 14 + 4 + 1 + 6 + 1 = 37 个文件（含 `get_node_list.py`）
- **OpenSpec archive**: 历史 archive 中的 `deputy-refactor-with-toml-config` change 描述的就是新管线方向，不动

# Comet Design Handoff

- Change: deputy-retire-legacy-pipeline
- Phase: design
- Mode: compact
- Context hash: d4ba0e6b2e061cd5dbaf6b91e5d86672777452dd4b4f26377dcd45f7e232ca0d

Generated-by: comet-handoff.sh

OpenSpec remains the canonical capability spec. This handoff is a deterministic, source-traceable context pack, not an agent-authored summary.

## openspec/changes/deputy-retire-legacy-pipeline/proposal.md

- Source: openspec/changes/deputy-retire-legacy-pipeline/proposal.md
- Lines: 1-29
- SHA256: e1dd2583a0c69c8f7cf30fdee23f5361d64804af8cd1bee76c2414fd13807b65

```md
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
```

## openspec/changes/deputy-retire-legacy-pipeline/design.md

- Source: openspec/changes/deputy-retire-legacy-pipeline/design.md
- Lines: 1-93
- SHA256: bfaf6d3905441862487c3a30a359230b6207cbf0cef96c2318a5f62de14a573e

[TRUNCATED]

```md
## Context

deputy 仓库当前有两条配置生成管线并存：

**老管线** — `get_node_list.py` 读 `templates/proxy-providers*.yaml` 和 `templates/rules_group*.yaml`，从 nite07 转换器拉订阅，下载到 `proxy_providers/*.yaml` 和 `rule_providers/*.yaml`，再用 `templates/head*.yaml` 拼接出 4 个平台配置（`clash_config_v3.yaml` / `config_mobile.yaml` / `config_mobile_baipiao.yaml` / `config_magisk.yaml`）。`.github/workflows/schedule-get-node-list.yml` 每 30 分钟触发，跑完后 commit 到 main。

**新管线** — `nodes.toml` → `scripts/sync_nodes.py` → `config.yaml` → GitHub Release `deputy-latest`。`.github/workflows/sync-and-release.yml` 每 3 小时触发。

2026-06-19 archived 的 `deputy-refactor-with-toml-config` change 确立了新管线的官方地位（`openspec/specs/toml-node-config/spec.md`）。但老管线的代码、配置、workflow、cron 触发都还在 main 上运行，每天向 main 注入 ~48 次"Update results from get_node_list.py" commit。

5 个使用 `https://clash.nite07.com/meta?nodeList=true&sub=...` 的订阅源在 `proxy_providers/` 中产生 3 字节 `{}` 文件，CI 静默成功，main 分支被无效 yaml 污染。

## Goals / Non-Goals

**Goals:**
- 仓库内不存在 `get_node_list.py`、`templates/`、`proxy_providers/`、`rule_providers/`
- 老管线 4 个输出配置（`clash_config_v3.yaml`、`config_mobile.yaml`、`config_mobile_baipiao.yaml`、`config_magisk.yaml`）从 main 删除
- `schedule-get-node-list.yml` 不再调度
- `config.template.yaml` 3 处 `path: ./rule_provider/` 单复数 typo 修正
- `openspec/specs/multi-platform-config/spec.md` 中 Desktop / Mobile / Magisk / Multi-platform concurrent 四个 requirement 删除，新增 Single pipeline generation requirement，并将剩余模板、校验、输出 requirement 收敛为单一 `config.yaml` 管线语义

**Non-Goals:**
- 不改 `nodes.toml`
- 不改 `scripts/sync_nodes.py` 及 `scripts/` 下任何文件
- 不改 `.github/workflows/sync-and-release.yml`
- 不改 `tests/` 任何文件
- 不改 OpenSpec archive 历史
- 不重构 `config.template.yaml` 的规则段（仅修 3 行 path typo）
- 不动 `rule_providers/` 的具体内容（直接删整个目录）

## Decisions

### D1. 单条 git commit 提交所有删除

**Why:** 这些文件之间是同生共死关系（脚本/输入/输出/触发器），分成多 commit 没有意义，merge review 时一个 diff 比 6 个 diff 易读。

**Alternative considered:** 分阶段（先删输出 → 再删输入 → 再删脚本）。拒绝：每阶段都让仓库处于半破状态，且对单用户单人维护项目过度工程。

### D2. 使用 delta spec 表达 capability 变更，archive 时更新 main spec

**Why:** 这个 change 是正式退役已有 capability 的行为，保留 `openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md` 能让 `openspec validate --strict` 和后续 `openspec archive` 有清晰依据。delta spec 负责表达删除多平台 requirement、新增单管线 generation requirement，以及把剩余 requirement 改写为单一 `config.yaml` 语义。

**Alternative considered:** 直接手改 main spec、不保留 delta。拒绝：会让 OpenSpec change 缺少可审计的 spec delta，也容易让 archive 阶段和设计文档互相打架。

### D3. `rule_providers/` 整目录删，保留并修正 3 个 http rule-provider path

**Why:** 用户选择"全删"老管线缓存目录。`config.template.yaml` 的 3 个 rule-providers 段是新管线输出配置的一部分，`type: http` 表示 Clash/mihomo 客户端可按 URL 自行拉取规则；这里删除的是仓库内缓存的 `rule_providers/` 目录，不删除规则能力本身。

**Trade-off:** 输出 `config.yaml` 仍包含本地缓存 path。修正为 `./rule_providers/...` 后语法和目录名一致，但仓库不再预置这些缓存文件，客户端首次使用时需要能访问对应 URL。

### D4. `config.template.yaml` typo 修正但保留 rule-providers 段

**Why:** 用户在澄清阶段选择"顺便修"。第 15/23/31 行的 `path: ./rule_provider/...` 改为 `./rule_providers/...`。**不删除**整段 rule-providers，因为：
- `scripts/sync_nodes.py` 渲染时整个 yaml 直接传给 template renderer，rule-providers 段作为字面量输出
- 删除需额外确认是否影响下游 Clash 客户端（rule-set 引用）

**Trade-off:** 输出 `config.yaml` 仍包含 3 个本地缓存 path；差异仅是把单数 typo 修成复数目录名。

### D5. `scripts/` 全部保留

**Why:** `grep -r "get_node_list\|proxy_providers" scripts/` 0 匹配，新管线已完全独立。`scripts/` 0 处需要改动。

### D6. OpenSpec archive 历史不删

**Why:** 2026-06-19 archived 的 `deputy-refactor-with-toml-config` 是历史记录，包含 `deputy-retire-legacy-pipeline` 的全部设计决策来源。archive 是只读时间戳，不应回改。

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| [Risk] 用户/脚本消费老的 4 个 config 文件 | [Mitigation] 验证场景 (e2e_smoke 不引用老路径); 用户在 AskUserQuestion 已确认老输出"无下游消费者" |
| [Risk] `git pull` 同步给其他协作者时大 diff | [Mitigation] 单 commit 一次性变更，比增量变更更易 review; 提前在 commit message 写明影响范围 |
| [Risk] `config.yaml` 渲染结果变化 | [Mitigation] 只改变 3 个 rule-provider cache path 的单复数 typo；运行 `scripts.sync_nodes` smoke test 验证模板仍可渲染 |
| [Risk] 老管线 schedule cron 删了后若想恢复需重建 | [Mitigation] git history 完整保留; 文档 README 写明新管线 |

## Migration Plan

单 PR 单 commit:

1. 删除文件（37 个）
```

Full source: openspec/changes/deputy-retire-legacy-pipeline/design.md

## openspec/changes/deputy-retire-legacy-pipeline/tasks.md

- Source: openspec/changes/deputy-retire-legacy-pipeline/tasks.md
- Lines: 1-48
- SHA256: d7fd937fe1950977b7056042eaa4670200248ac67aa72eb31e5098ec213b3c1a

```md
## 1. Reference grep audit (前置防御性检查)

- [ ] 1.1 全仓库 grep 确认老管线 0 引用 (脚本: `grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" . | grep -v "openspec/changes/deputy-retire-legacy-pipeline" | grep -v "openspec/changes/archive" | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md"`)

## 2. 老管线脚本与目录删除

- [ ] 2.1 删除 `get_node_list.py`
- [ ] 2.2 删除 `proxy_providers/` 整个目录 (11 个 yaml)
- [ ] 2.3 删除 `rule_providers/` 整个目录 (14 个 yaml)
- [ ] 2.4 删除 `templates/` 整个目录 (6 个 yaml: head.yaml / head_mobile.yaml / proxy-providers.yaml / proxy-providers_baipiao.yaml / rules_group.yaml / rules_group_mobile.yaml)

## 3. 老管线输出配置删除

- [ ] 3.1 删除 `clash_config_v3.yaml`
- [ ] 3.2 删除 `config_mobile.yaml`
- [ ] 3.3 删除 `config_mobile_baipiao.yaml`
- [ ] 3.4 删除 `config_magisk.yaml`

## 4. 老管线 workflow 删除

- [ ] 4.1 删除 `.github/workflows/schedule-get-node-list.yml`

## 5. config.template.yaml typo 修复

- [ ] 5.1 第 15 行 `path: ./rule_provider/AWAvenue-Ads.yaml` → `path: ./rule_providers/AWAvenue-Ads.yaml`
- [ ] 5.2 第 23 行 `path: ./rule_provider/StevenBlack.yaml` → `path: ./rule_providers/StevenBlack.yaml`
- [ ] 5.3 第 31 行 `path: ./rule_provider/Adguard-Adblock.yaml` → `path: ./rule_providers/Adguard-Adblock.yaml`

## 6. multi-platform-config spec 收敛为单 config.yaml 语义

- [ ] 6.1 删除 `openspec/specs/multi-platform-config/spec.md` 中 Desktop platform configuration generation requirement
- [ ] 6.2 删除 Mobile platform configuration generation requirement
- [ ] 6.3 删除 Magisk platform configuration generation requirement
- [ ] 6.4 删除 Multi-platform concurrent generation requirement
- [ ] 6.5 新增 Single pipeline configuration generation requirement
- [ ] 6.6 将 Template-based configuration generation 改写为单一 `config.yaml` 模板渲染 requirement
- [ ] 6.7 将 Configuration validation 改写为单一输出 YAML 校验 requirement
- [ ] 6.8 将 Configuration output management 改写为 `config.yaml` Release artifact 输出管理 requirement

## 7. 验证

- [ ] 7.1 `grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" . | grep -v "openspec/changes/deputy-retire-legacy-pipeline" | grep -v "openspec/changes/archive" | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md"` → 0 匹配
- [ ] 7.2 `uv run python -m scripts.sync_nodes --config nodes.toml --template config.template.yaml --output /tmp/test-config.yaml --previous /tmp/test-prev.yaml` → 退出码 0, 生成非空 config
- [ ] 7.3 `uv run pytest tests/` → 全绿

## 8. Commit

- [ ] 8.1 `git add -A` + `git commit -m "chore(deputy): retire legacy get_node_list.py pipeline, keep only nodes.toml → sync_nodes.py"`
```

## openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md

- Source: openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md
- Lines: 1-73
- SHA256: 8a481c178a6fe5113c57809c73005acd9395b91780994c9f5a8236d76d360495

```md
## REMOVED Requirements

### Requirement: Desktop platform configuration generation
**Reason**: 退役老 `get_node_list.py` 管线后, 仓库仅保留 `nodes.toml` → `scripts/sync_nodes.py` → `config.yaml` 单管线输出. 不再区分 desktop / mobile / magisk 等多平台配置. 详见 change `deputy-retire-legacy-pipeline`.
**Migration**: 单一 `config.yaml` 兼容 mihomo 桌面端与移动端; 不再需要平台分叉配置.

### Requirement: Mobile platform configuration generation
**Reason**: 同 Desktop requirement — 老管线已退役, 不再生成 `config_mobile.yaml`.
**Migration**: 使用 `config.yaml` (发布到 GitHub Release `deputy-latest`) 即可在移动端 mihomo 使用.

### Requirement: Magisk platform configuration generation
**Reason**: 同 Desktop requirement — 老管线已退役, 不再生成 `config_magisk.yaml`.
**Migration**: Magisk 模块用户需自封装 `config.yaml`, 或上游模块维护者自行 fork.

### Requirement: Multi-platform concurrent generation
**Reason**: 退役老管线后, 仓库不再并发生成多个平台变体. 新管线只生成一个 canonical `config.yaml`.
**Migration**: 使用单管线生成的 `config.yaml`; 不再依赖平台分叉输出或并发生成语义.

## ADDED Requirements

### Requirement: Single pipeline configuration generation
The system SHALL generate one publishable Mihomo configuration through the `nodes.toml` to `config.yaml` pipeline.

#### Scenario: Single output generation
- **WHEN** the scheduled sync pipeline runs
- **THEN** the system renders one `config.yaml` output
- **AND** the system does not generate desktop, mobile, baipiao, or magisk variant files

#### Scenario: Shared node data
- **WHEN** generating `config.yaml`
- **THEN** the system uses the shared node data from `nodes.toml` and configured subscription sources
- **AND** the system applies one consistent transformation for all consumers

## MODIFIED Requirements

### Requirement: Template-based configuration generation
The system SHALL use `config.template.yaml` as the single source template for generating `config.yaml`.

#### Scenario: Template variable substitution
- **WHEN** the system processes `config.template.yaml`
- **THEN** the system substitutes node placeholders with data from `nodes.toml` and subscription fetch results
- **AND** the system preserves the static template sections, including http rule-providers and rule definitions

#### Scenario: Single template selection
- **WHEN** the system generates the publishable configuration
- **THEN** the system uses only `config.template.yaml`
- **AND** the system does not require platform-specific template files under `templates/`

### Requirement: Configuration validation
The system SHALL validate the generated `config.yaml` before publication.

#### Scenario: YAML syntax validation
- **WHEN** the system generates `config.yaml`
- **THEN** the system validates YAML syntax for that output file
- **AND** the system reports syntax errors before publication

#### Scenario: Single output validation
- **WHEN** validation completes
- **THEN** the system treats `config.yaml` as the only required publishable configuration artifact
- **AND** the system does not require validation of removed platform-specific outputs

### Requirement: Configuration output management
The system SHALL manage `config.yaml` as the canonical generated configuration output.

#### Scenario: Output file organization
- **WHEN** the system writes generated configuration
- **THEN** the system writes the publishable file as `config.yaml`
- **AND** the system makes that artifact available through the release pipeline

#### Scenario: Output file consistency
- **WHEN** generating `config.yaml`
- **THEN** the system keeps node ordering and rendered template sections deterministic
- **AND** the system avoids creating legacy platform-specific configuration files
```


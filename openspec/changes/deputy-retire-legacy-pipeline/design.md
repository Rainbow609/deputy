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
2. 修改 `config.template.yaml` 3 行 typo
3. 通过 delta spec 修改 `multi-platform-config`：删 4 个多平台 requirement，新增单管线 generation requirement，并把剩余 requirement 改写为单一 `config.yaml` 语义
4. 验证：
   - `grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" . | grep -v "openspec/changes/deputy-retire-legacy-pipeline" | grep -v "openspec/changes/archive" | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md"` → 0 匹配
   - `uv run python -m scripts.sync_nodes --config nodes.toml --template config.template.yaml --output /tmp/test-config.yaml --previous /tmp/test-prev.yaml` → 退出码 0
   - `uv run pytest tests/` → 全绿
5. commit message: `chore(deputy): retire legacy get_node_list.py pipeline, keep only nodes.toml → sync_nodes.py`

**Rollback:** `git revert <commit>` 即可恢复全部 37 个文件 + 2 处文本修改 — 这是减法变更，无前向兼容负担。

## Open Questions

- 无。用户已在 AskUserQuestion 阶段对所有边界情况拍板。

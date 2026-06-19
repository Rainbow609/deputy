---
comet_change: deputy-retire-legacy-pipeline
role: technical-design
canonical_spec: openspec
archived-with: 2026-06-19-deputy-retire-legacy-pipeline
status: final
---

# Deputy 退役老管线 — 技术设计文档

## 概述

本文档是 change `deputy-retire-legacy-pipeline` 的技术设计。所有决策已经在 OpenSpec 阶段（`openspec/changes/deputy-retire-legacy-pipeline/`）由用户拍板，本文档不引入新设计决策，只做"实施级"落地说明。

**范围性质**：纯减法 + 1 个模板文件的 3 行文本修正。不新增 capability、不改架构、不引入依赖。

**OpenSpec canonical spec**: `openspec/changes/deputy-retire-legacy-pipeline/`（proposal.md / design.md / specs/multi-platform-config/spec.md / tasks.md）。本文档不复制 spec 内容，仅描述实施层面。

## 边界确认（无需新设计决策）

下列边界已在 OpenSpec open 阶段 AskUserQuestion 由用户明确选择，本节仅记录以便 build 阶段对照执行：

| 边界 | 决策 | 来源 |
|------|------|------|
| `rule_providers/` 处理 | 整目录删 | open 阶段 AskUserQuestion 选项 1（用户已选） |
| `multi-platform-config` spec 处理 | delta spec 表达 REMOVED + ADDED + MODIFIED 3 类变更 | open 阶段 AskUserQuestion 选项 2 + linter 微调后定型 |
| `config.template.yaml` typo | 第 15/23/31 行 `./rule_provider/` → `./rule_providers/` | open 阶段 AskUserQuestion 选项 1（用户已选） |
| 旧管线输出文件 | 4 个全部删除 | 用户输入明示 |
| `nodes.toml` | 不动 | 用户输入明示 |
| `scripts/` | 不动 | OpenSpec design D5（grep 0 引用） |
| `.github/workflows/sync-and-release.yml` | 不动 | OpenSpec design Non-Goals |
| OpenSpec archive 历史 | 不动 | OpenSpec design D6 |

## 实施分解

### 阶段 A：删除文件（37 个文件）

```
[Stage A.1] 脚本
  get_node_list.py                                              # 1

[Stage A.2] 目录（rm -rf）
  proxy_providers/                                              # 11 yaml
  rule_providers/                                               # 14 yaml (注: linter 把 15 修正为 14, 见 tasks.md)
  templates/                                                    # 6 yaml

[Stage A.3] 老输出配置
  clash_config_v3.yaml
  config_mobile.yaml
  config_mobile_baipiao.yaml
  config_magisk.yaml

[Stage A.4] 老 workflow
  .github/workflows/schedule-get-node-list.yml
```

**顺序约束**：先删 workflow（A.4）可防止老管线在删除中途被 cron 重新触发并 commit — 减法变更中这是"小但关键"的实施细节。

### 阶段 B：文本修正（2 文件）

**B.1** `config.template.yaml` — 3 行 typo：

| 行 | 旧 | 新 |
|----|----|----|
| 15 | `path: ./rule_provider/AWAvenue-Ads.yaml` | `path: ./rule_providers/AWAvenue-Ads.yaml` |
| 23 | `path: ./rule_provider/StevenBlack.yaml` | `path: ./rule_providers/StevenBlack.yaml` |
| 31 | `path: ./rule_provider/Adguard-Adblock.yaml` | `path: ./rule_providers/Adguard-Adblock.yaml` |

**B.2** `openspec/specs/multi-platform-config/spec.md` — delta spec 已在 change 目录（`openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md`）就绪，归档阶段由 `comet-archive` 脚本把 delta 合入 main spec。不在 build 阶段手改 main spec 文件 — 保持 delta→main 的单向审计。

### 阶段 C：验证

1. **引用 grep 守卫** — 排除 OpenSpec/docs 历史与当前产物后，对运行路径中的老路径 0 匹配
2. **smoke render** — `python -m scripts.sync_nodes` 在 nodes.toml 现有内容下能成功跑完（防止误删影响新管线）
3. **pytest** — 全绿

### 阶段 D：Commit

核心实现单 commit。OpenSpec/docs 状态整理可追加独立 cleanup commit。Commit message 见 `tasks.md` 8.1。

## 风险与防护

| 实施风险 | 防护 |
|----------|------|
| 删除中途老 workflow 又跑一次 | 阶段 A 内先删 workflow (A.4) 再删其他 |
| grep 验证漏判（OpenSpec/docs 产物内有历史引用） | 显式排除 current change、archive、main spec、当前 plan/design doc 和历史 design doc |
| 误删 `config.template.yaml` 中 rule-providers 整段 | tasks.md 5.1-5.3 只改 path 字段，不动其他；Build 阶段 diff review 必看 |
| main spec 提前被手改 | 严格走 delta → archive 流程，build 阶段不动 main spec |

## 关键不实施项（明示）

- **不写 README 更新章节** — README 已被 grep 确认不含老路径引用，无更新必要
- **不写 e2e smoke 新增 case** — 现有 e2e_smoke 0 引用老路径，删除后继续通过即可
- **不发新 release** — `sync-and-release.yml` 不变，按现有 3h cron 自然产生下一个 `deputy-latest`
- **不删 GitHub Release 历史** — 旧 release asset 仍在，但内容不会被 `config.yaml` 替换（`fail_on_unmatched_files: false`）

## OpenSpec → Build 衔接

- `tasks.md` 是 build 阶段唯一执行清单；`archive-tasks.md` 仅记录 archive 阶段待办
- 本文档不复制 task 列表，避免双源同步漂移
- Build 阶段工作方式（subagent-driven / direct）由 build 阶段用户选择决定

## 归档衔接（archive 阶段预告）

`comet-archive` 阶段将自动：
1. 把 delta spec（REMOVED 4 个 + ADDED 1 个 + MODIFIED 3 个）合入 `openspec/specs/multi-platform-config/spec.md`
2. 更新 `docs/superpowers/specs/2024-06-18-deputy-refactor-design.md` 标注 `archived-with`
3. 更新本文档 frontmatter 写入 `archived-with: 2026-06-19-deputy-retire-legacy-pipeline`
4. 移动整个 change 目录到 `openspec/changes/archive/`

Build 阶段不需要为这些动作预留任何接口。

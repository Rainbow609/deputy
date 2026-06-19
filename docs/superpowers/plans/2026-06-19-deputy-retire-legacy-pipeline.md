---
change: deputy-retire-legacy-pipeline
design-doc: docs/superpowers/specs/2026-06-19-deputy-retire-legacy-pipeline-design.md
base-ref: 7d0a6d3158a059b17500f46cb56a90675ba5e2fc
archived-with: 2026-06-19-deputy-retire-legacy-pipeline
---

# Deputy 退役老管线 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 从 main 分支删除老 `get_node_list.py` 管线（脚本、缓存目录、模板目录、老输出配置、cron workflow），修正 `config.template.yaml` 中 3 处单复数 typo，并准备 delta spec 供 archive 阶段合入 main spec。

**Architecture:** 纯减法 + 1 个模板文件的 3 行文本修正。删除顺序关键 — 先删 cron workflow 防止删除中途老管线被重新触发并 commit。delta spec 已就绪在 `openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md`，build 阶段不动 `openspec/specs/multi-platform-config/spec.md`（由 archive 脚本合入）。

**Tech Stack:** Bash / git / Python (smoke render) / pytest

---

## 范围与不变项

**变更范围（build 阶段全部产物）：**
- 删除 37 个文件（其中 31 个位于 `proxy_providers/`、`rule_providers/`、`templates/` 三个目录内）
- 修改 `config.template.yaml` 3 行
- 核心实现单 commit 提交；OpenSpec/docs 状态整理可追加独立 cleanup commit

**明确不动：**
- `nodes.toml` — 用户明示不动
- `scripts/` — grep 0 引用（D5）
- `.github/workflows/sync-and-release.yml` — Non-Goals
- `tests/` — Non-Goals
- `openspec/specs/multi-platform-config/spec.md` — 由 archive 脚本处理（D2）
- `openspec/changes/archive/` — 历史不动（D6）
- `docs/superpowers/specs/2024-06-18-deputy-refactor-design.md` — 历史不动

**无 TDD 循环**：被删除的代码无对应测试，新管线测试已存在且不受影响。验证采用 3 项现有手段（grep / smoke render / pytest）。

---

## 文件结构图

| 路径 | 类型 | 来源 |
|------|------|------|
| `get_node_list.py` | 删 | 阶段 A.1 |
| `proxy_providers/` (11 yaml) | 删 | 阶段 A.2 |
| `rule_providers/` (14 yaml) | 删 | 阶段 A.2 |
| `templates/` (6 yaml) | 删 | 阶段 A.2 |
| `clash_config_v3.yaml` | 删 | 阶段 A.3 |
| `config_mobile.yaml` | 删 | 阶段 A.3 |
| `config_mobile_baipiao.yaml` | 删 | 阶段 A.3 |
| `config_magisk.yaml` | 删 | 阶段 A.3 |
| `.github/workflows/schedule-get-node-list.yml` | 删 | 阶段 A.4 |
| `config.template.yaml` | 改 3 行 | 阶段 B.1 |
| `openspec/specs/multi-platform-config/spec.md` | **不动** | archive 阶段处理 |

---

## 任务依赖图

```
Task 1 (前置 grep audit)
  └─> Task 2 (删 workflow A.4)        ← 必须最先删, 防 cron 重跑
        └─> Task 3 (删脚本 A.1)
              └─> Task 4 (删 3 个目录 A.2)
                    └─> Task 5 (删 4 个老输出 A.3)
                          └─> Task 6 (改 config.template.yaml B.1)
                                └─> Task 7 (3 项验证)
                                      └─> Task 8 (commit)
```

**关键顺序**：Task 2 (workflow) 必须在 Task 3/4/5 之前。否则老 cron 可能在删除过程中触发并 commit 已被部分删除的代码到 main。

---

## Task 1: 前置 grep audit — 确认老管线 0 引用

**Files:**
- Read-only: 全仓库

- [x] **Step 1: 执行 grep 守卫脚本**

Run:
```bash
cd /Users/liangzongyou/git/deputy
grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" \
  . \
  | grep -v "openspec/changes/deputy-retire-legacy-pipeline" \
  | grep -v "openspec/changes/archive" \
  | grep -v "openspec/specs/multi-platform-config/spec.md" \
  | grep -v "docs/superpowers/plans/2026-06-19-deputy-retire-legacy-pipeline.md" \
  | grep -v "docs/superpowers/specs/2026-06-19-deputy-retire-legacy-pipeline-design.md" \
  | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md"
```

Expected: 仅命中 `get_node_list.py` 自身、`proxy_providers/`、`templates/`、`clash_config_v3.yaml`、`config_mobile*.yaml`、`config_magisk.yaml`、`.github/workflows/schedule-get-node-list.yml` 这些**将被删除的文件**。**无其他文件**命中（特别是 `scripts/`、`tests/`、`nodes.toml`、`config.template.yaml`、`.github/workflows/sync-and-release.yml` 不应出现）。

- [x] **Step 2: 人工确认命中文件都是待删除目标**

逐行检查 grep 输出，确认所有命中行都是被 Task 3/4/5 删除的目标文件之一。如果发现意外命中（如 `scripts/`、`config.template.yaml` 内的 `proxy_providers` 引用），**立即停止并向用户报告** — 这意味着设计假设（"新管线无老路径引用"）不成立。

- [x] **Step 3: 记录基准（可选）**

若希望保留审计痕迹供后续对照：
```bash
cd /Users/liangzongyou/git/deputy
grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" \
  . \
  | grep -v "openspec/changes/deputy-retire-legacy-pipeline" \
  | grep -v "openspec/changes/archive" \
  | grep -v "openspec/specs/multi-platform-config/spec.md" \
  | grep -v "docs/superpowers/plans/2026-06-19-deputy-retire-legacy-pipeline.md" \
  | grep -v "docs/superpowers/specs/2026-06-19-deputy-retire-legacy-pipeline-design.md" \
  | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md" \
  | wc -l
```

Expected: build 完成后数字 = 0。pre-build 审计阶段只要求命中均属于待删除目标，不依赖固定行数。

**注意**：本 Task 不产生 commit。这是 build 前的事实记录，不属于 change 本身的产物。

---

## Task 2: 删除老管线 workflow（最先执行）

**Files:**
- Delete: `.github/workflows/schedule-get-node-list.yml`

- [x] **Step 1: 删除文件**

Run:
```bash
cd /Users/liangzongyou/git/deputy
rm .github/workflows/schedule-get-node-list.yml
```

- [x] **Step 2: 验证文件已删除**

Run:
```bash
ls -la /Users/liangzongyou/git/deputy/.github/workflows/schedule-get-node-list.yml 2>&1
```

Expected: `No such file or directory` 错误。

- [x] **Step 3: 验证 .github/workflows/ 仍含 sync-and-release.yml**

Run:
```bash
ls /Users/liangzongyou/git/deputy/.github/workflows/
```

Expected: 仅 `sync-and-release.yml`。

**重要**：本 Task 不单独 commit，与 Task 3/4/5/6 合并为单 commit（见 Task 8）。但物理删除顺序必须如此 — 防 cron 触发。

---

## Task 3: 删除老管线脚本 `get_node_list.py`

**Files:**
- Delete: `get_node_list.py`

- [x] **Step 1: 删除文件**

Run:
```bash
cd /Users/liangzongyou/git/deputy
rm get_node_list.py
```

- [x] **Step 2: 验证文件已删除**

Run:
```bash
ls -la /Users/liangzongyou/git/deputy/get_node_list.py 2>&1
```

Expected: `No such file or directory` 错误。

---

## Task 4: 删除 3 个老管线目录

**Files:**
- Delete: `proxy_providers/` (11 yaml)
- Delete: `rule_providers/` (14 yaml)
- Delete: `templates/` (6 yaml)

- [x] **Step 1: 删除 3 个目录**

Run:
```bash
cd /Users/liangzongyou/git/deputy
rm -rf proxy_providers/ rule_providers/ templates/
```

- [x] **Step 2: 验证目录已删除**

Run:
```bash
ls -d /Users/liangzongyou/git/deputy/proxy_providers/ /Users/liangzongyou/git/deputy/rule_providers/ /Users/liangzongyou/git/deputy/templates/ 2>&1
```

Expected: 3 个 `No such file or directory` 错误。

- [x] **Step 3: 统计删除文件数（健全性检查）**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git status --short | wc -l
```

Expected: 已暂存或未跟踪的删除项累计应达到 ~31（11 + 14 + 6），加 Task 2/3 累计 ~33。具体数字以 `git status` 输出为准，**只要不为 0 即正常**。

---

## Task 5: 删除 4 个老管线输出配置

**Files:**
- Delete: `clash_config_v3.yaml`
- Delete: `config_mobile.yaml`
- Delete: `config_mobile_baipiao.yaml`
- Delete: `config_magisk.yaml`

- [x] **Step 1: 删除 4 个文件**

Run:
```bash
cd /Users/liangzongyou/git/deputy
rm clash_config_v3.yaml config_mobile.yaml config_mobile_baipiao.yaml config_magisk.yaml
```

- [x] **Step 2: 验证文件已删除**

Run:
```bash
cd /Users/liangzongyou/git/deputy
ls clash_config_v3.yaml config_mobile.yaml config_mobile_baipiao.yaml config_magisk.yaml 2>&1
```

Expected: 4 个 `No such file or directory` 错误。

- [x] **Step 3: 确认无其他老管线残留**

Run:
```bash
cd /Users/liangzongyou/git/deputy
ls | grep -E "^(clash_config_v3|config_mobile|config_mobile_baipiao|config_magisk)\.yaml$" 2>&1
echo "---"
ls | grep -E "^(get_node_list\.py|proxy_providers|rule_providers|templates)" 2>&1
```

Expected: 两个 `grep` 均为空输出。

---

## Task 6: 修改 `config.template.yaml` — 3 行 path typo 修正

**Files:**
- Modify: `config.template.yaml` (lines 15, 23, 31)

- [x] **Step 1: 确认当前内容**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -n '15p;23p;31p' config.template.yaml
```

Expected:
```
    path: ./rule_provider/AWAvenue-Ads.yaml
    path: ./rule_provider/StevenBlack.yaml
    path: ./rule_provider/Adguard-Adblock.yaml
```

- [x] **Step 2: 替换 3 行 — 行 15**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -i 's|path: \./rule_provider/AWAvenue-Ads\.yaml|path: ./rule_providers/AWAvenue-Ads.yaml|' config.template.yaml
```

- [x] **Step 3: 替换 3 行 — 行 23**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -i 's|path: \./rule_provider/StevenBlack\.yaml|path: ./rule_providers/StevenBlack.yaml|' config.template.yaml
```

- [x] **Step 4: 替换 3 行 — 行 31**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -i 's|path: \./rule_provider/Adguard-Adblock\.yaml|path: ./rule_providers/Adguard-Adblock.yaml|' config.template.yaml
```

- [x] **Step 5: 验证替换结果**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -n '15p;23p;31p' config.template.yaml
```

Expected:
```
    path: ./rule_providers/AWAvenue-Ads.yaml
    path: ./rule_providers/StevenBlack.yaml
    path: ./rule_providers/Adguard-Adblock.yaml
```

- [x] **Step 6: 确认仅这 3 行变化（diff 检查）**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git diff config.template.yaml
```

Expected: diff 恰好 6 行（3 行 `-` + 3 行 `+`），无其他变更。若出现其他变更，**立即停止并向用户报告** — sed 命令可能误伤了模板其他部分。

- [x] **Step 7: 确认 rule-providers 段未误删**

Run:
```bash
cd /Users/liangzongyou/git/deputy
sed -n '10,34p' config.template.yaml
```

Expected: 整个 `rule-providers:` 块仍然完整（10-34 行），仅 path 字段从单数改为复数。

---

## Task 7: 验证（3 项）

**Files:**
- Read-only: 全仓库
- Test: `scripts/sync_nodes.py` smoke render
- Test: `tests/` pytest

- [x] **Step 1: grep 守卫 — 老路径 0 引用**

Run:
```bash
cd /Users/liangzongyou/git/deputy
grep -rn "get_node_list\|proxy_providers\|clash_config_v3\|config_magisk\|config_mobile_baipiao\|schedule-get-node-list" \
  --include="*.py" --include="*.yml" --include="*.yaml" --include="*.toml" --include="*.md" \
  . \
  | grep -v "openspec/changes/deputy-retire-legacy-pipeline" \
  | grep -v "openspec/changes/archive" \
  | grep -v "openspec/specs/multi-platform-config/spec.md" \
  | grep -v "docs/superpowers/plans/2026-06-19-deputy-retire-legacy-pipeline.md" \
  | grep -v "docs/superpowers/specs/2026-06-19-deputy-retire-legacy-pipeline-design.md" \
  | grep -v "docs/superpowers/specs/2024-06-18-deputy-refactor-design.md"
```

Expected: **空输出**（0 匹配）。任何匹配都意味着遗漏或隐藏引用。

- [x] **Step 2: smoke render — `scripts/sync_nodes.py` 跑通**

Run:
```bash
cd /Users/liangzongyou/git/deputy
uv run python -m scripts.sync_nodes --config nodes.toml --template config.template.yaml --output /tmp/test-config.yaml --previous /tmp/test-prev.yaml
echo "exit=$?"
ls -la /tmp/test-config.yaml
wc -l /tmp/test-config.yaml
```

Expected:
- `exit=0`
- `/tmp/test-config.yaml` 存在
- 行数 > 0（具体取决于 nodes.toml 当前内容，至少 100+ 行）

- [x] **Step 3: pytest — 全绿**

Run:
```bash
cd /Users/liangzongyou/git/deputy
uv run pytest tests/
```

Expected: 所有测试通过，无 FAILED。若有失败，**停止 commit 并调查** — 即使被删除的代码无测试，新管线测试也可能因路径变更受影响。

- [x] **Step 4: 清理 smoke render 临时文件**

Run:
```bash
rm -f /tmp/test-config.yaml /tmp/test-prev.yaml
```

**注意**：本 Task 不产生 commit。验证是 commit 前的事实门控。

---

## Task 8: 单 commit 提交

**Files:**
- Stage all: 上述 37 个删除 + 1 个文本修改

- [x] **Step 1: 查看 git status 确认变更范围**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git status --short
```

Expected: 仅包含以下类型的条目：
- `D  get_node_list.py`
- `D  proxy_providers/<file>.yaml` (11 行)
- `D  rule_providers/<file>.yaml` (14 行)
- `D  templates/<file>.yaml` (6 行)
- `D  clash_config_v3.yaml`
- `D  config_mobile.yaml`
- `D  config_mobile_baipiao.yaml`
- `D  config_magisk.yaml`
- `D  .github/workflows/schedule-get-node-list.yml`
- `M  config.template.yaml`

**禁止出现**：对 `nodes.toml`、`scripts/`、`tests/`、`openspec/specs/multi-platform-config/spec.md`、`.github/workflows/sync-and-release.yml` 的任何变更。若出现，**停止并向用户报告**。

- [x] **Step 2: 暂存所有变更**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git add -A
git status --short | head -5
```

Expected: 第一行输出以 `M ` 或 `D ` 开头（前缀字母大小写因 git 版本而异，关键是显示已暂存）。

- [x] **Step 3: 提交（单 commit）**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git commit -m "chore(deputy): retire legacy get_node_list.py pipeline, keep only nodes.toml → sync_nodes.py"
```

Expected: commit 成功，commit message 显示完整文本。

- [x] **Step 4: 验证 commit**

Run:
```bash
cd /Users/liangzongyou/git/deputy
git log --oneline -3
git show --stat HEAD | tail -50
```

Expected:
- `git log` 最顶行包含 `chore(deputy): retire legacy...`
- `git show --stat HEAD` 列出 ~37 个变更文件（35 删除 + 1 修改 + 1 workflow 删除 = 37 个文件条目）

> **推送（Step 5）从本 plan 中移除**：plan 范围 = 协调者跑完 commit 即结束。push 决策由用户在 build 阶段结束后的 verify 之前拍板（`git push origin feature/20260619/deputy-retire-legacy-pipeline`），不在本 plan 自动范围内。

---

## 完成清单

build 阶段完成的客观证据：

- [x] Task 1 grep audit 通过（仅命中待删除目标）
- [x] Task 2 `.github/workflows/schedule-get-node-list.yml` 已物理删除
- [x] Task 3 `get_node_list.py` 已删除
- [x] Task 4 `proxy_providers/`、`rule_providers/`、`templates/` 三个目录已删除
- [x] Task 5 4 个老输出配置已删除
- [x] Task 6 `config.template.yaml` 仅 3 行 path 字段变更
- [x] Task 7 grep 0 匹配 + smoke render exit=0 + pytest 全绿
- [x] Task 8 核心实现 commit 已落地，commit message 准确

---

## 不实施项（明示）

- **不写 README 更新章节** — README 已被 grep 确认不含老路径引用，无更新必要
- **不写 e2e smoke 新增 case** — 现有 e2e_smoke 0 引用老路径，删除后继续通过即可
- **不发新 release** — `sync-and-release.yml` 不变，按现有 3h cron 自然产生下一个 `deputy-latest`
- **不删 GitHub Release 历史** — 旧 release asset 仍在，但内容不会被 `config.yaml` 替换（`fail_on_unmatched_files: false`）
- **不改 main spec 文件** — `openspec/specs/multi-platform-config/spec.md` 由 archive 阶段脚本合入，build 阶段不动
- **不新增测试** — 本计划无需 TDD 循环，无需 unit test 编写，无需 e2e 新增。验证 3 项（grep / smoke render / pytest）已存在
- **不重构 `config.template.yaml` 的规则段** — 仅修 3 行 path typo

---

## 归档衔接（archive 阶段预告，非本计划范围）

build 完成后，`comet-archive` 阶段将自动：
1. 把 delta spec（REMOVED 4 个 + ADDED 1 个 + MODIFIED 3 个）合入 `openspec/specs/multi-platform-config/spec.md`
2. 更新 `docs/superpowers/specs/2024-06-18-deputy-refactor-design.md` 标注 `archived-with`
3. 更新本文档 frontmatter 写入 `archived-with: 2026-06-19-deputy-retire-legacy-pipeline`
4. 移动整个 change 目录到 `openspec/changes/archive/`

Build 阶段不需要为这些动作预留任何接口。

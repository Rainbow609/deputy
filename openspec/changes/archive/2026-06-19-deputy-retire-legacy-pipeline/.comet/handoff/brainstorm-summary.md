# Brainstorm Summary

- Change: deputy-retire-legacy-pipeline
- Date: 2026-06-19

## 为什么跳过 brainstorming

范围性质 = 纯减法 + 2 处文本修正。**无新架构决策**。全部边界（rule_providers/ 全删、main spec 走 delta、typo 修）在 OpenSpec open 阶段 AskUserQuestion 已由用户拍板。6 个 Design Decisions 全部在 OpenSpec design.md 里写明。

执行 brainstorming 只会让用户重述已经定的事实，违反 "Don't add features beyond what was asked" 原则。

## 已确认的技术方案

- **删除顺序**：先 workflow → 再脚本 → 再目录 → 再输出 yaml（防止老管线 cron 在中途重新触发并 commit）
- **commit 策略**：单 commit 单 PR（OpenSpec design D1）
- **main spec 收敛**：走 delta → archive 流程，build 阶段不动 main spec 文件
- **typo 修复**：`config.template.yaml` 第 15/23/31 行 path 字段单数→复数，rule-providers 整段保留（不影响 sync_nodes.py 渲染）

## 关键取舍与风险

| 取舍/风险 | 决定 |
|-----------|------|
| rule_providers/ 全删 vs 保留 | 全删（用户拍板） |
| main spec 改法 | 走 delta spec（用户拍板） |
| typo 顺手修 | 是（用户拍板） |
| 删除中途 cron 重跑 | 阶段 A 内先删 workflow |
| 减法变更无前向兼容负担 | rollback = `git revert` 即可 |

## 测试策略

- 引用 grep 守卫（排除 change/archive/legacy design doc）
- `uv run python -m scripts.sync_nodes` smoke 渲染（防误删影响新管线）
- `uv run pytest tests/` 全绿

## Spec Patch

无（delta spec 已在 change 创建阶段就绪，归档阶段合入 main spec）。

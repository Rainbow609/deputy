# Archive Phase Tasks (build 阶段外)

以下 8 个 task 由 `comet-archive` 阶段处理, build 阶段不动 `openspec/specs/multi-platform-config/spec.md` (设计 D2)。

## A.1 main spec 合入 (由 comet-archive 脚本执行)

- [ ] A.1.1 把 `openspec/changes/deputy-retire-legacy-pipeline/specs/multi-platform-config/spec.md` 的 REMOVED Requirements (4 项: Desktop / Mobile / Magisk / Multi-platform concurrent) 写入 `openspec/specs/multi-platform-config/spec.md`
- [ ] A.1.2 把 ADDED Requirements (1 项: Single pipeline configuration generation) 写入 main spec
- [ ] A.1.3 把 MODIFIED Requirements (3 项: Template-based / Configuration validation / Configuration output management) 改写后写入 main spec
- [ ] A.1.4 验证 main spec 语法/格式与 OpenSpec 校验器一致 (`openspec validate --strict`)

## A.2 archive metadata 收尾

- [ ] A.2.1 在 `docs/superpowers/specs/2024-06-18-deputy-refactor-design.md` frontmatter 标注 `related: 2026-06-19-deputy-retire-legacy-pipeline`
- [ ] A.2.2 在本文档 frontmatter 写入 `archived-with: 2026-06-19-deputy-retire-legacy-pipeline`
- [ ] A.2.3 移动整个 change 目录到 `openspec/changes/archive/`
- [ ] A.2.4 删除分支 `feature/20260619/deputy-retire-legacy-pipeline` (可选, 由用户决定)

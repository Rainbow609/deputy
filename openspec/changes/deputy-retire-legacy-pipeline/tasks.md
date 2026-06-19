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

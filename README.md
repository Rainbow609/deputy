# deputy

多源 Clash Meta 配置生成器，基于 mihomo-config 架构。

## 特性

- **TOML 配置** — `nodes.toml` 统一管理静态节点和订阅源
- **多源拉取** — cloudscraper → requests → curl_cffi 自动 fallback
- **节点验证** — TCP 探活 + 延迟测试，过滤不可用节点
- **质量统计** — 存活率、延迟分布、变更追踪
- **GitHub Releases** — 有更新时自动发布

## 使用方式

1. 编辑 `nodes.toml`，填入你的订阅源
2. 本地运行：`uv run python -m scripts.sync_nodes`
3. 生成的 `config.yaml` 即为最终配置

## CI/CD

`.github/workflows/sync-and-release.yml` 每 3 小时自动运行一次，
发现配置变更时自动创建 GitHub Release。

订阅地址格式：

```
https://github.com/<user>/<repo>/releases/latest/download/config.yaml
```

## 详细文档

- 节点配置: [docs/nodes-toml-guide.md](docs/nodes-toml-guide.md)
- 技术设计: [docs/superpowers/specs/2024-06-18-deputy-refactor-design.md](docs/superpowers/specs/2024-06-18-deputy-refactor-design.md)
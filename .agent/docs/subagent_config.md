# Subagent 模型配置

该配置文件列出了 Subagent 可选的模型类型，主 Agent 会读取这个配置文件。

注意：需要在 `~/.codex/config.toml` 文件中配置模型的 Key，否则将无法启用模型。

## 可选模型

- gpt-5.2-codex（通用、稳定）
- gpt-4.1-mini（轻量、快速）

## 使用方式

- 在调用脚本时由主 Agent 选择合适模型

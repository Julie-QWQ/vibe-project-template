# Subagent 模型配置

该配置文件列出了 Subagent 可选的执行引擎和模型，主 Agent 会读取这个配置文件并据此选择合适的执行方式。

## 执行引擎类型

`run_subagent.py` 支持两种执行引擎，通过 `--engine` 参数选择：

### Codex CLI 引擎（`--engine codex`）

通过 Codex CLI 工具执行 Subagent，适合使用本地或第三方模型。

**配置要求**：

- 需要在 `~/.codex/config.toml` 中为每个 profile 配置对应的模型、provider 等信息
- 使用 `--profile <profile-name>` 参数选择模型
- 使用 `--sandbox <mode>` 参数指定沙盒模式（read-only / workspace-write / danger-full-access）

**可用 Profiles**：

| Profile Name | 说明 |
|-------------|------|
| `deepseek-v3.2` | DeepSeek V3.2 模型 |
| `glm-4.7` | 智谱 GLM-4.7 模型 |

**使用示例**：

```bash
python .agent/tools/run_subagent.py \
  --engine codex \
  --profile deepseek-v3.2 \
  --sandbox workspace-write \
  --phase phase-001 --task task-001 --subagent subagent-001
```

### Claude API 引擎（`--engine claude`）

直接调用 Anthropic Claude API，使用官方 Tool Use 接口。

**配置要求**：

- 需要设置 `ANTHROPIC_API_KEY` 环境变量，或使用 `--api-key` 参数
- 使用 `--model <model-name>` 参数选择模型
- 自动记录 token 使用情况（total_tokens / prompt_tokens / completion_tokens）

**可用 Models**：

| Model Name | 模型 ID | 说明 |
|-----------|--------|------|
| `claude-sonnet-4-5-20250929` | Claude Sonnet 4.5 | 平衡性能和成本，适合大多数任务 |

**使用示例**：

```bash
# 设置 API key
export ANTHROPIC_API_KEY=your_key_here

# 运行 Subagent
python .agent/tools/run_subagent.py \
  --engine claude \
  --model claude-sonnet-4-5-20250929 \
  --phase phase-001 --task task-001 --subagent subagent-001
```

## 模型选择建议

- **简单任务**（如代码生成、文档编写）：使用 Codex CLI + deepseek-v3.2（成本低）
- **复杂度任务**：使用 Claude API + claude-sonnet-4-5-20250929（平衡）

## 引擎特性对比

| 特性 | Codex CLI | Claude API |
|-----|-----------|------------|
| Token 记录 | ❌ 不支持 | ✅ 自动记录 |
| 沙盒模式 | ✅ 支持三种模式 | ❌ 不支持 |
| 成本 | 取决于配置的模型 | 按 Anthropic 定价 |
| Tool Use | 取决于模型能力 | 原生支持 |
| 网络要求 | 取决于配置的模型 | 需要 Anthropic API 访问 |

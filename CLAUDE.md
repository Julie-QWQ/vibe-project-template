# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **Vibe-Coding Project Template** - a framework implementing a hierarchical "Master Agent + Subagent" architecture for AI-assisted software development. The framework enforces strict separation between planning (Master Agent) and execution (Subagents), with all operations recorded in an audit trail.

## Agent Architecture

### Role: Master Agent (主 Agent)

- **Responsible for**: Planning, task breakdown, delegation, and quality control
- **NOT allowed to**: Directly modify code, configuration files, or generate artifacts
- **Communication**: Only via structured JSON files (request.json/response.json)
- **Reference**: [Agent.md](.agent/docs/Agent.md) - Complete behavior specification

### Role: Subagent

- **Responsible for**: Executing specific development tasks as delegated by Master Agent
- **Operates in**: Sandboxed environments with configurable security levels
- **Output**: Structured JSON response with execution results
- **Instructions**: [subagent_prompt.md](.agent/docs/subagent_prompt.md)

### Audit Mechanism

All Subagent calls must be recorded in `.agent/audit/` with structure:

```
.agent/audit/phase-xxx/task-xxx/subagent-xxx/
├── request.json    # Task delegation from Master Agent
├── response.json   # Execution result from Subagent
├── stderr.txt      # Process output
└── info.md         # Metadata (profile, timestamp)
```

## Directory Structure

| Directory | Purpose |
|-----------|---------|
| [`.agent/`](.agent/) | Framework core |
| [`.agent/docs/`](.agent/docs/) | Agent behavior documentation ([Agent.md](.agent/docs/Agent.md), [subagent_config.md](.agent/docs/subagent_config.md), [subagent_prompt.md](.agent/docs/subagent_prompt.md)) |
| [`.agent/templates/`](.agent/templates/) | JSON request/response templates |
| [`.agent/tools/`](.agent/tools/) | **Subagent 工具**: [run_subagent.py](.agent/tools/run_subagent.py) 主入口，lib/ 目录包含核心模块 |
| [`.agent/audit/`](.agent/audit/) | Execution history (organized by phase/task/subagent) |
| [`docs/`](docs/) | Project documentation (ToDo, requirements, design) |
| [`src/`](src/) | Project source code |
| [`scripts/`](scripts/) | Utility scripts |

## Common Commands

### 运行 Subagent

**重要**: 使用 `--engine` 参数选择执行引擎（默认: `codex`）

#### 使用 Codex CLI 执行

```bash
python .agent/tools/run_subagent.py \
  --phase phase-001 \
  --task task-001 \
  --subagent subagent-001 \
  --engine codex \
  --profile deepseek-v3.2 \
  --sandbox workspace-write
```

#### 使用 Claude API 执行

```bash
python .agent/tools/run_subagent.py \
  --phase phase-001 \
  --task task-001 \
  --subagent subagent-001 \
  --engine claude \
  --model claude-sonnet-4-5-20250929
```

**Note**: Claude engine 需要 `ANTHROPIC_API_KEY` 环境变量或 `--api-key` 参数。

### Module-Level Commands (Developer Use)

以下命令仅供开发者调试或自定义工作流使用。Master Agent 应直接调用 [run_subagent.py](.agent/tools/run_subagent.py)。

#### Initialize Audit Directory

```bash
python .agent/tools/lib/modules/init_audit_dir.py --phase phase-001 --task task-001 --subagent subagent-001
# Output: request.json and response.json paths
```

#### Validate Request File

```bash
python .agent/tools/lib/modules/validate_request.py .agent/audit/phase-001/task-001/subagent-001/request.json
# Exit code 0 if valid, 1 if invalid
```

#### Execute Subagent (Codex CLI)

```bash
python .agent/tools/lib/modules/run_subagent_exec.py \
  --request .agent/audit/phase-001/task-001/subagent-001/request.json \
  --response .agent/audit/phase-001/task-001/subagent-001/response.json \
  --profile deepseek-v3.2 \
  --sandbox workspace-write
```

#### Execute Subagent (Claude API)

```bash
python .agent/tools/lib/modules/run_subagent_claude.py \
  --request .agent/audit/phase-001/task-001/subagent-001/request.json \
  --response .agent/audit/phase-001/task-001/subagent-001/response.json \
  --model claude-sonnet-4-5-20250929
```

**Note**: Requires `ANTHROPIC_API_KEY` environment variable or `--api-key` parameter.

#### Validate Response File

```bash
python .agent/tools/lib/modules/validate_response.py .agent/audit/phase-001/task-001/subagent-001/response.json
# Exit code 0 if valid, 1 if invalid
```

### Key Parameters

#### 通用参数（所有引擎）

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--engine` | 执行引擎: `codex` 或 `claude` | `codex` |
| `--phase` | Phase 名称（如 phase-001） | - |
| `--task` | Task 名称（如 task-001） | - |
| `--subagent` | Subagent 名称（如 subagent-001） | - |
| `--request` | 直接指定 request.json 路径 | - |
| `--response` | 直接指定 response.json 路径 | - |
| `--audit-root` | Audit 目录根路径 | `.agent/audit` |

#### Codex CLI 专用参数（`--engine codex`）

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--profile` | Codex 配置 profile（从 [subagent_config.md](.agent/docs/subagent_config.md) 选择） | Codex 默认 |
| `--sandbox` | 沙盒模式: `read-only`, `workspace-write`, `danger-full-access` | - |
| `--codex-cmd` | Codex CLI 命令路径 | `codex.cmd` (Windows) / `codex` (Linux) |
| `--cd` | 工作目录 | `.` |
| `--skip-git-repo-check` | 跳过 git 仓库检查 | - |
| `--idle-timeout` | 无输出超时时间（秒） | 60 |
| `--codex-args` | 额外的 Codex 参数 | - |

#### Claude API 专用参数（`--engine claude`）

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--model` | Claude 模型（如 `claude-sonnet-4-5-20250929`） | `claude-sonnet-4-5-20250929` |
| `--api-key` | Anthropic API key（或设置 `ANTHROPIC_API_KEY` 环境变量） | - |
| `--cd` | 工作目录 | `.` |

### 使用示例

#### Codex CLI - 完整参数示例

```bash
python .agent/tools/run_subagent.py \
  --phase phase-001 \
  --task task-001 \
  --subagent subagent-001 \
  --engine codex \
  --profile deepseek-v3.2 \
  --sandbox workspace-write \
  --idle-timeout 120
```

#### Claude API - 完整参数示例

```bash
# 设置 API key
export ANTHROPIC_API_KEY=your_key_here

# 运行 Subagent
python .agent/tools/run_subagent.py \
  --phase phase-001 \
  --task task-001 \
  --subagent subagent-001 \
  --engine claude \
  --model claude-opus-4-5-20251101
```

## Task Organization

### Hierarchy

- **Phase**: Logical grouping of related tasks (one phase ≈ one conversation session)
- **Task**: Individual work unit with clear acceptance criteria
- **Subagent**: Single execution of a task (a task may require multiple subagent attempts)

### Request JSON Structure

Based on [template_request.json](.agent/templates/template_request.json):

```json
{
  "version": "1.0",
  "task_id": "",
  "task": "",
  "context": {
    "files": [],
    "notes": ""
  },
  "constraints": [],
  "expected_output": {
    "description": "",
    "format": "json",
    "schema": {}
  },
  "acceptance_criteria": []
}
```

### Response JSON Structure

Based on [template_response.json](.agent/templates/template_response.json):

```json
{
  "version": "1.0",
  "task_id": "",
  "status": "",
  "summary": "",
  "outputs": [],
  "validation": [],
  "issues": []
}
```

## Model Selection

### Codex CLI Profiles

Available profiles are defined in [subagent_config.md](.agent/docs/subagent_config.md):

| Profile | Description |
|---------|-------------|
| `deepseek-v3.2` | DeepSeek V3.2 model |
| `glm-4.7` | GLM-4.7 model |

### Claude API Models

Available Claude models for `run_subagent_claude.py`:

| Model | Description |
|-------|-------------|
| `claude-sonnet-4-5-20250929` | Claude Sonnet 4.5 (balanced) |
| `claude-opus-4-5-20251101` | Claude Opus 4.5 (most capable) |

**Critical**:

- For Codex CLI: Use `--profile <profile-name>`, profiles configured in `~/.codex/config.toml`
- For Claude API: Use `--model <model-name>`, requires `ANTHROPIC_API_KEY`

## Critical Constraints

1. **No Direct Code Modification**: Master Agent must NOT directly edit code - delegate to Subagents via request.json
2. **Audit Trail Required**: Every Subagent call must create an entry in `.agent/audit/`
3. **JSON-Only Communication**: Master Agent and Subagent communicate ONLY through request.json/response.json
4. **Request First**: Master Agent must create request.json BEFORE calling run_subagent.py
5. **Validation Required**: Master Agent must verify response.json against acceptance criteria and initiate rework if failed
6. **Profile Selection**: Use only profiles from [subagent_config.md](.agent/docs/subagent_config.md)

## Workflow Reference

1. Master Agent 调用 [run_subagent.py](.agent/tools/run_subagent.py)（唯一入口）
2. run_subagent.py 自动创建审计目录
3. run_subagent.py 验证 request.json
4. run_subagent.py 执行 Subagent（内部调用 lib/modules/ 中的执行模块）
5. run_subagent.py 验证 response.json
6. Master Agent 审核 response.json，如失败则创建新的 subagent 目录进行返工

## Key Files for Understanding

### Master Agent 必读

| File | Purpose |
|------|---------|
| [Agent.md](.agent/docs/Agent.md) | Master Agent 行为规范和约束 |
| [subagent_prompt.md](.agent/docs/subagent_prompt.md) | Subagent 行为指令 |
| [subagent_config.md](.agent/docs/subagent_config.md) | 可用模型配置（Codex & Claude） |
| [run_subagent.py](.agent/tools/run_subagent.py) | **主入口**：Master Agent 唯一需要调用的脚本 |
| [template_request.json](.agent/templates/template_request.json) | Request JSON 格式规范 |
| [template_response.json](.agent/templates/template_response.json) | Response JSON 格式规范 |

### 开发者参考（内部实现）

| File | Purpose |
|------|---------|
| [lib/modules/__init__.py](.agent/tools/lib/modules/__init__.py) | 模块包初始化 |
| [lib/modules/init_audit_dir.py](.agent/tools/lib/modules/init_audit_dir.py) | 初始化审计目录 |
| [lib/modules/validate_request.py](.agent/tools/lib/modules/validate_request.py) | 验证 request.json |
| [lib/modules/run_subagent_exec.py](.agent/tools/lib/modules/run_subagent_exec.py) | 通过 Codex CLI 执行 |
| [lib/modules/run_subagent_claude.py](.agent/tools/lib/modules/run_subagent_claude.py) | 通过 Claude API 执行 |
| [lib/modules/validate_response.py](.agent/tools/lib/modules/validate_response.py) | 验证 response.json |
| [lib/__init__.py](.agent/tools/lib/__init__.py) | 共享工具函数 |
| [README.md](README.md) | 项目结构和工作流概述 |

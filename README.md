# Vibe-Coding 项目骨架说明

本文档用于说明本项目的总体结构、使用方式与协作流程，帮助新成员快速理解如何开展 Vibe-Coding 工作。

## 1. 项目目标

本项目提供一套“主 Agent + Subagent”的协作框架。主 Agent 负责任务拆解与调度，Subagent 负责执行具体任务，并通过结构化 JSON 进行任务委派与结果反馈。所有执行过程需在 audit 目录中留档，便于追踪与复盘。

## 2. 核心概念

- **phase / step / round**：用于组织执行过程的层级。
  - 一个 phase 对应一轮对话/目标。
  - 一个 step 对应一个任务。
  - 一个 round 对应一次 Subagent 调用。
- **request.json / response.json**：
  - request.json：主 Agent 委派任务的结构化输入。
  - response.json：Subagent 返回执行结果的结构化输出。
- **.agent/audit/**：所有 Subagent 调用的归档目录，按 `phase/step/round` 组织。

## 3. 目录结构

```
.
├─ .agent/                   # Agent 相关
│  ├─ docs/                  # Agent 文档
│  │  ├─ Agent.md
│  │  └─ subagent_config.md
│  ├─ templates/             # request/response 模板
│  │  ├─ template_request.json
│  │  └─ template_response.json
│  ├─ tools/                 # Subagent 调用脚本
│  │  └─ run_subagent.py
│  └─ audit/                 # 执行留档（phase/step/round）
├─ docs/                     # 项目需求/设计/ToDo 文档
│  ├─ ToDo.md
│  ├─ 项目需求文档.md
│  └─ 项目设计文档.md
├─ src/                      # 项目源码（按实际项目填充）
└─ README.md            # 本说明文档
```

## 4. 使用流程

1. **准备 ToDo**
   - 在 `docs/ToDo.md` 中按“模块 → phase → task”编写任务清单。
2. **创建 audit 目录与 request.json**
   - 在 `.agent/audit/phase-xxx/step-xxx/round-xxx/` 下创建 `request.json`。
   - request.json 需遵循 `.agent/templates/template_request.json` 的字段结构。
3. **执行 Subagent**
   - 使用 `.agent/tools/run_subagent.py` 调用 Subagent。
   - 两种调用方式（二选一）：
     - 通过 phase/step/round 自动创建目录：
       - `python .agent/tools/run_subagent.py --phase phase-001 --step step-001 --round round-001`
     - 直接指定路径：
       - `python .agent/tools/run_subagent.py --request .agent/audit/phase-001/step-001/round-001/request.json --response .agent/audit/phase-001/step-001/round-001/response.json`
4. **验收与返工**
   - 主 Agent 读取 `response.json`，按验收标准判断成功/失败。
   - 若失败，开启新的 round 继续执行。

## 5. 模型选择

主 Agent 可根据任务复杂度选择合适模型。可选模型列表在 `.agent/docs/subagent_config.md` 中维护，调用时通过 `--model` 参数指定。

## 6. 角色职责

- **主 Agent**：负责计划、拆解、委派与验收，不直接修改代码。
- **Subagent**：严格按 request.json 执行任务，并输出 response.json。

## 7. 关键约束

- 所有 Subagent 调用必须写入 `.agent/audit/` 目录。
- request.json 必须由主 Agent 预先创建。
- Subagent 输出必须为结构化 JSON。

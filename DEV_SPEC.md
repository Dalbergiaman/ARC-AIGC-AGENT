# AIGC Agent — 建筑效果图生成系统

> 每次对话开始时请读取本文件，了解项目当前状态。

---

## 项目概述

通过多轮对话逐步探讨建筑效果图细节，支持用户上传参考图，最终生成高质量建筑效果图。

---

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | TypeScript + Next.js (App Router) |
| 后端 | Python + FastAPI |
| Agent 框架 | LangGraph |
| MCP 框架 | FastMCP（`mcp.server.fastmcp`，官方 mcp 库内置） |
| 对话模型 | 百炼（Qwen3-VL）/ 火山引擎豆包 VLM，Dashboard 可切换，支持视觉理解 |
| 图像生成 | 云端 API：阿里云百炼（万相）/ 火山引擎（即梦）/ GrsAI |
| 数据库 | PostgreSQL + SQLAlchemy |
| LangGraph Checkpointer | PostgreSQL（langgraph-checkpoint-postgres） |
| 任务队列 | Celery + Redis |
| 文件存储 | 本地开发 / MinIO 生产 |
| 前端状态 | Zustand |
| 前端 UI | Tailwind CSS + shadcn/ui |
| 可观测性 | Langfuse（LLM 调用追踪；Prompt 本地 git 版本管理） |
| Milvus 管理 | Attu（Milvus 可视化管理界面，`http://localhost:8080`） |

---

## 整体架构

```
用户浏览器
    │
    ▼
Next.js 前端 (TypeScript)
    │  REST API + SSE（流式对话）
    ▼
FastAPI 后端 (Python)
    ├── LangGraph Agent（对话编排 + 状态管理）
    ├── 图像生成模块（Celery 异步队列）
    └── 文件存储模块
         │
         ├── VLM（百炼 Qwen3-VL / 火山引擎豆包 VLM，视觉理解）
         ├── 图像生成（云端 API：百炼 / 豆包 / GrsAI）
         └── 对象存储（本地 / MinIO / S3）
```

---

## 项目目录结构

```
aigc_agent/
├── DEV_SPEC.md                         # 本文件
├── docker-compose.yml
├── image-rag-mcp/                      # 独立 MCP 服务（stdio 通信）
│   ├── main.py                         # uv 初始化入口（占位，未使用；实际入口 server.py）
│   ├── server.py                       # FastMCP stdio 入口，lifespan 串 PG + Milvus，注册 5 个工具
│   ├── config.py                       # 环境变量 / dashboard.yaml / 维度常量
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── store.py                    # store_generated_image：下载副本 → caption → 双 embedding → PG + Milvus
│   │   ├── search.py                   # search_by_text / search_by_image（短 URL 自动反解为本地文件）
│   │   └── retrieve.py                 # get_image_by_id（PG 全字段）
│   ├── core/
│   │   ├── __init__.py
│   │   ├── embedding/                  # Embedding 模块（独立文件夹）
│   │   │   ├── base.py                 # 抽象基类 TextEmbeddingClientBase / ImageEmbeddingClientBase
│   │   │   ├── volcengine_text.py      # 火山引擎 doubao-embedding-vision 文本输入客户端
│   │   │   ├── volcengine_image.py     # 火山引擎 doubao-embedding-vision 图像输入客户端
│   │   │   └── factory.py              # TextEmbeddingFactory / ImageEmbeddingFactory
│   │   ├── vlm_caption.py              # 复用 dashboard.yaml LLM 调 VLM 生成检索用中文 caption
│   │   ├── milvus_client.py            # Milvus 操作封装（HNSW/COSINE + INVERTED 索引、insert / search）
│   │   ├── pg_client.py                # PostgreSQL 操作封装（image_library 表 CRUD）
│   │   └── storage.py                  # library_images/ 副本管理：save_source_url / library_url_for / resolve_library_url
│   ├── library_images/                 # 图库本地副本（gitignored），按 {image_id}.{ext} 存储
│   ├── scripts/                        # 各阶段 stdio E2E smoke（test_d1_smoke / test_d1_stdio / test_d2_smoke / test_d3_stdio）
│   └── pyproject.toml                  # uv 项目配置
├── frontend/                           # Next.js 前端
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── chat/[sessionId]/page.tsx
│   │   └── dashboard/page.tsx          # Dashboard：模型配置、API Key 管理
│   ├── components/
│   │   ├── chat/                       # 规划：E-1/E-2 新增三栏对话组件
│   │   │   ├── ChatWorkspace.tsx       # 规划：三栏对话工作台容器
│   │   │   ├── AppSidebar.tsx          # 规划：左侧栏：历史对话 / 知识库 / 首页跳转 / 折叠
│   │   │   ├── ChatPanel.tsx           # 规划
│   │   │   ├── MessageList.tsx         # 规划
│   │   │   ├── InputBar.tsx            # 规划
│   │   │   └── ImageUploader.tsx       # 规划
│   │   ├── workspace/                  # 规划：E-2/E-4 新增右侧工作区组件
│   │   │   ├── WorkspacePanel.tsx      # 规划：Prompt / 生成图标签页
│   │   │   ├── PromptReferenceTab.tsx  # 规划：提示词展示、参考图上传、参数滑块、风格模板
│   │   │   ├── GeneratedImagesTab.tsx  # 规划：生成图展示、批注入口、下载
│   │   │   ├── ReferenceIntentPicker.tsx # 规划
│   │   │   ├── GenerationControls.tsx  # 规划
│   │   │   └── ImageAnnotationCanvas.tsx # 规划
│   │   ├── gallery/                    # 规划：如保留独立图库展示组件再新增
│   │   │   └── ResultGallery.tsx       # 规划
│   │   └── dashboard/
│   │       ├── ModelSelector.tsx       # 对话模型选择（百炼/火山引擎 VLM）
│   │       ├── ImageProviderConfig.tsx # 图像生成平台配置（百炼万相/火山即梦/GrsAI）
│   │       └── ApiKeyForm.tsx          # API Key 填写与保存
│   ├── hooks/
│   │   ├── useChat.ts                  # 规划
│   │   ├── useSSE.ts                   # 规划
│   │   └── useImageGeneration.ts       # 规划
│   ├── store/
│   │   ├── chatStore.ts                # 规划
│   │   └── workspaceStore.ts           # 规划：右侧工作区 UI 状态与前端草稿
│   └── lib/
│       ├── api.ts
│       └── types.ts
└── backend/                            # FastAPI 后端
    ├── main.py
    ├── config.py
    ├── pyproject.toml                  # uv 项目配置
    ├── api/
    │   └── routes/
    │       ├── chat.py
    │       ├── generation.py           # 规划：独立生成任务查询接口（当前未实现）
    │       ├── library.py              # 规划：图库存储 REST 接口，后端直接调用 image-rag-mcp
    │       ├── upload.py
    │       ├── session.py
    │       └── dashboard.py            # Dashboard 配置接口
    ├── agent/                          # LangGraph Agent
    │   ├── graph.py                    # Agent 图定义（核心）
    │   ├── state.py                    # AgentState 定义
    │   ├── checkpointer.py             # PostgreSQL checkpointer 初始化
    │   ├── prompts.py                  # 所有节点/工具的 Prompt 函数，本地版本管理（git）
    │   └── tools/
    │       ├── image_analysis.py       # analyze_reference_image — 视觉 LLM 分析参考图
    │       ├── prompt_builder.py       # enhance_prompt + refine_prompt — Prompt 构建与修正
    │       ├── image_generator.py      # generate_image — 调用 core/image/generator
    │       ├── image_evaluator.py      # evaluate_generated_image — 视觉 LLM 评估生成结果
    │       ├── search_library.py       # search_similar_cases — 调用 image-rag-mcp 检索
    │       └── prompt_templates.py     # 纯数据文件：9 种风格关键词库，供 /api/styles/templates 与 agent_system 建议提示使用
    ├── core/
    │   ├── llm/
    │   │   ├── base.py                 # 抽象基类 LLMClientBase
    │   │   ├── factory.py              # LLMClientFactory（bailian / volcengine）
    │   │   ├── bailian_client.py       # 百炼 VLM 客户端（Qwen3-VL 等）
    │   │   ├── volcengine_client.py    # 火山引擎豆包 VLM 客户端
    │   │   ├── client.py               # 调度器，从 dashboard.yaml 读取当前模型
    │   │   └── streaming.py            # SSE 流式输出处理
    │   └── image/
    │       ├── generator.py            # 图像生成调度器（多平台统一接口）
    │       ├── base.py                 # 抽象基类 ImageGeneratorBase + 统一数据结构
    │       ├── factory.py              # ImageGeneratorFactory
    │       ├── bailian_client.py       # 阿里云百炼（Qwen）客户端
    │       ├── volcengine_client.py    # 火山引擎豆包客户端
    │       └── grsai_client.py         # GrsAI 客户端
    ├── services/
    │   ├── session_service.py
    │   ├── message_service.py
    │   ├── storage_service.py
    │   └── dashboard_service.py        # Dashboard 配置读写（backend/config/dashboard.yaml）
    ├── config/
    │   ├── dashboard.yaml              # Dashboard 配置（含 API Key，.gitignore 忽略）
    │   └── dashboard.yaml.example     # 配置模板（提交到 git）
    └── models/
        ├── database.py
        └── schemas.py
```

---

## LangGraph Agent 设计

### AgentState（工作记忆）

`AgentState` 继承 LangGraph 的 `MessagesState`（本身是 `TypedDict` 子类），`messages` 字段自动附加 `add_messages` reducer，保证多轮对话历史追加而非覆盖。

```python
class AgentState(MessagesState):  # MessagesState 是带 add_messages reducer 的 TypedDict
    design_state: DesignState            # 结构化设计参数（工作记忆核心）
    reference_images: list[ReferenceImageAnalysis]  # 参考图分析结果
    control_image: ControlImage | None   # 图生图结构底图（单张），用于约束建筑体量/透视/尺度/空间关系
    annotated_image: AnnotatedImage | None  # 批注后的上一版效果图，用于下一轮图生图调整
    ready_to_generate: bool              # 控制流：是否触发生成
    generation_results: list[GenerationResult]      # 历史生成结果
    retry_count: int                     # 当前生成任务的重试次数（上限 3，每次新生成意图重置）
    last_evaluation: EvaluationResult | None        # 最近一次评估结果
    similar_cases: list[ImageRecord]     # RAG 检索到的参考案例
    last_search_signature: dict | None   # 上次 RAG 检索使用的核心设计参数
    best_generation_result: GenerationResult | None  # 当前生成任务的最高分结果
    current_task_id: str | None          # 当前 Celery 任务 ID
    phase: Literal["collecting", "generating", "evaluating", "interrupted", "done"]
    turn_id: str                         # 本轮用户消息 ID；当前 C-6.1 实现临时写入 session_id
    run_id: str                          # 本轮 Agent 执行 ID，用于取消与断线重连
```

所有子结构（`DesignState`、`ReferenceImageAnalysis`、`GenerationResult`、`EvaluationResult`、`ImageRecord`）均使用 `TypedDict` 定义，确保 LangGraph checkpointer JSON 序列化兼容。

### Agent 层子结构定义

> 注意：`GenerationResult` 在 Agent 层（`agent/state.py`）和图像生成层（`core/image/base.py`）各有一份定义，含义不同。Agent 层的版本额外包含 `score` 字段（评估分数），是评估完成后的完整记录；生成层的版本只含生成本身的原始结果。

```python
class ReferenceImageAnalysis(TypedDict, total=False):
    image_url: str
    building_type: str
    style: str
    facade_material: str
    lighting: str
    viewpoint: str
    color_palette: str
    description: str
    reference_intent: str  # composition / color / style / material / lighting / surroundings / other
    intent_note: str       # 用户对参考意图的补充说明

class ControlImage(TypedDict, total=False):
    file_id: str
    image_url: str
    note: str
    sent: bool

class AnnotatedImage(TypedDict, total=False):
    file_id: str
    image_url: str
    note: str
    sent: bool

class GenerationResult(TypedDict, total=False):  # Agent 层，含评估分数
    image_url: str
    provider: str
    generation_time: float
    score: float          # 评估后填入，生成层 GenerationResult 无此字段
    raw_response: dict

class ImageRecord(TypedDict):
    id: str
    image_url: str
    caption: str
    prompt: str
    design_state: dict
    provider: str
```

### 前端工作区状态映射

前端三栏工作台中的右侧工作区不是新的 Agent 决策中心，而是 `AgentState` / SSE 事件 / 用户草稿的可视化编辑层。后端仍以 `DesignState`、`reference_images`、`_enhanced_prompt` 和 `generation_results` 作为权威状态；前端在用户点击发送或生成时，将草稿内容随消息提交给 Agent。

工作区前端草稿结构（TypeScript）：

```ts
type WorkspaceDraft = {
  keywords: Record<string, string>
  llm_description: string
  custom_description: string
  negative_prompt: string
  prompt_template: {
    style: string
    positive: string[]
    negative: string[]
    mood: string
    description: string
  } | null
  referenceImages: Array<{
    fileId: string
    url: string
    intent: "composition" | "color" | "style" | "material" | "lighting" | "surroundings" | "other"
    note?: string
  }>
  generationParams: {
    temperature?: number
    lightingIntensity?: number
    stylization?: number
    materialStrength?: number
    compositionStrength?: number
  }
}
```

约束：
- E-1 先实现 UI 状态和 SSE 展示，不要求所有滑块立即影响真实生成 API。
- E-2/E-3 当前临时实现：参考图草稿与结构化 prompt 草稿按 `sessionId` 存 `localStorage`，用于单浏览器刷新/关闭后恢复。
- E-3.5 起必须把会话业务状态迁移到 PostgreSQL：结构化 prompt 草稿、已上传参考图、已生成图片结果应随 session 服务端恢复；`localStorage` 只保留布局偏好和未提交的临时 UI 状态。
- 提示词展示优先消费 `prompt_update` / `enhance_prompt` 结果；`keywords`、`llm_description`、`custom_description`、`negative_prompt`、`prompt_template` 整份结构化草稿必须作为 session 业务状态保存。用户手动编辑后的 prompt 需作为下一轮消息上下文传回 Agent，避免只停留在前端。

### 持久化边界（E-3.5 起执行）

| 状态 | 当前实现 | 目标持久化 | 原因 |
|------|----------|------------|------|
| 会话列表 / 标题 | PostgreSQL `sessions` | PostgreSQL | 历史会话核心数据 |
| 聊天消息 | PostgreSQL `messages` | PostgreSQL | 历史对话核心数据 |
| 结构化 prompt 草稿（`keywords` / `llm_description` / `custom_description` / `negative_prompt` / `prompt_template`） | `localStorage.promptDraftBySession` | PostgreSQL，建议存 `sessions.workspace_state` JSON 或等价字段 | 与 session 强绑定，应跨浏览器/设备恢复 |
| 已上传参考图（`fileId` / `url` / `intent` / `note` / `sent` / `analysis`） | `localStorage.referenceImagesBySession` + AgentState | PostgreSQL `reference_images.analysis` JSON | 参考图是会话输入资产，不应只存在浏览器 |
| 生成图结果（任务 ID、prompt、negative prompt、image_url、provider、score、raw_response） | 前端内存 `generationPreviews` + AgentState | PostgreSQL `generation_tasks` 或扩展后的生成结果表 | E-4 生成图片区刷新后必须可恢复 |
| 右侧栏宽度、折叠状态、当前 tab | 前端内存 / 可选 localStorage | `localStorage` | 浏览器 UI 偏好，不属于业务状态 |
| 上传中、错误提示、当前 SSE stream、工具状态 | 前端内存 | 不持久化 | 临时运行状态，刷新后应重新计算或丢弃 |

### DesignState 结构

```python
class DesignState(TypedDict, total=False):
    building_type: str        # 建筑类型（别墅/商业/办公...）
    style: str                # 风格（极简/新中式/工业风...）
    facade_material: str      # 外立面材质
    lighting: str             # 光线（时段/方向/氛围）
    viewpoint: str            # 视角（人视/鸟瞰/仰视...）
    season: str               # 季节/天气
    surroundings: str         # 周边环境
    color_palette: str        # 色彩倾向
    special_requirements: str # 特殊需求
    missing_fields: list[str] # 仍需补充的关键字段
    field_confidence: dict[str, float]  # 每个字段的置信度 0.0~1.0
    completeness: float       # 由规则计算的信息完整度 0.0~1.0，不直接信任 LLM 自评
```

### Graph 节点与流转（Agent 决策 + 确定性生成子流程）

完整流程图见 `agent_graph.mmd`。

Agent 不完全依赖 ReAct 自由调用完整生成链路。单一 `agent` 节点负责理解用户意图、更新 `DesignState`、判断是否需要补充信息、是否进入生成；一旦进入生成，Graph 走确定性子流程，避免漏评估、重复生成或过早重试。

```
用户消息
  → agent（更新 DesignState / 判断意图 / 必要时调用轻量工具）
  → 若信息不足：回复追问
  → 若需要生成：
      → rag_gate（按规则判断是否调用 search_similar_cases）
      → enhance_prompt
      → generate_image
      → evaluate_generated_image
      → score < 0.8 且 retry_count < 3：refine_prompt → generate_image → evaluate_generated_image
      → 返回 best_generation_result
```

**关键设计点：**

- `store_generated_image` 不是 Agent 工具，由前端图片卡片下方的「存入图库」按钮触发，调用独立 REST 接口 `POST /api/library/store`，后端直接调 MCP，不经过 Agent。
- 每轮用户消息创建新的 `turn_id` 和 `run_id`；`retry_count`、`best_generation_result`、`current_task_id` 只作用于当前生成任务，新生成意图开始时重置。
- `agent` 可自主调用轻量工具（如 `analyze_reference_image`、`search_similar_cases`），但图像生成、评估、重试由确定性子流程控制。
- 风格关键词不再由 Agent 自动注入：`agent_node` 不再根据 `design_state.style` 自动查库注入，`enhance_prompt` 也不再反查。风格模板只通过前端用户显式选择的 `prompt_template` 注入到 `agent_system` 与 `enhance_prompt_system`；用户未选时 `agent_system` 仅展示可用模板列表，允许 LLM 在 `reply` 中口头建议用户在右侧选择。
- 图像生成入口由后端显式用户意图规则硬把关：只有用户最新一轮消息明确要求生成 / 出图 / 渲染（含 generate / render / create image 等英文命令）时，才允许 `ready_to_generate` 进入生成子流程；LLM 输出的 `ready_to_generate` 不能单独触发生成，且“不要生成 / 先不生成 / do not generate”等否定表达优先拦截。
- 所有会影响控制流的 LLM 输出必须通过 Pydantic schema 校验；解析失败时返回可恢复错误或走保守兜底。

**工具说明**

| 工具 | 输入 | 输出 | 调用时机 |
|------|------|------|----------|
| `analyze_reference_image` | image_url | ReferenceImageAnalysis | 用户上传参考图后 |
| `search_similar_cases` | query, filters | list[ImageRecord] | agent 信息收集阶段，RAG 参考 |
| `enhance_prompt` | design_state, reference_analysis, similar_cases, prompt_template | EnhancedPrompt | 信息充分，首次生成前 |
| `generate_image` | enhanced_prompt, ref_image_url | GenerationResult | 每次触发生成 |
| `evaluate_generated_image` | image_url, design_state, reference_images | EvaluationResult | 每次生成后自动评估 |
| `refine_prompt` | original_prompt, evaluation | EnhancedPrompt | 评估不满意时修正 |

> 历史工具 `lookup_style_keywords` 已于 2026-05-10 移除：风格关键词库不再由 Agent 自动反查，仅通过前端用户显式选择的 `prompt_template` 注入；`STYLE_LIBRARY` 继续通过 `/api/styles/templates` 供前端模板选择使用。

> `store_generated_image` 不在此列：由前端按钮触发 `POST /api/library/store`，不经过 Agent。

### Graph 边界控制

| 边界 | 机制 | 参数 | 兜底行为 |
|------|------|------|----------|
| 生成重试上限 | 当前生成任务的 `retry_count` 字段计数 | 最多 3 次 | 返回 `best_generation_result` |
| 工具调用总步数 | LangGraph `recursion_limit` | 25 步 | 当前依赖上层异常处理；返回当前最优结果的兜底需后续补齐 |
| 用户中断 | Redis cancel flag + LangGraph `interrupt_before` | 轮询内可中断；`interrupt_before` 已配置但 chat 路由尚未恢复旧 run | 不计入 `retry_count`，新消息启动新 run |
| 评估分数兜底 | `retry_count == 3` 时返回当前最佳结果 | `best_generation_result` | 当前 state 保留最佳结果；用户可见的"最大重试"文案需前端/Agent 回复补齐 |
| 结构化输出 | Pydantic schema 校验 | 工具内解析失败重试 1 次 | prompt/evaluator 已有 fallback；agent 节点 JSON 解析失败走追问兜底 |

**用户中断实现说明**：当前主链路用 Redis `active_run:{session_id}` 记录会话正在运行的 `run_id`；收到新消息时设置上一轮 `cancel:{session_id}:{run_id}`。`generate_image` 轮询内检查 cancel flag 并抛 `CancelledError`。`interrupt_before=["agent"]` 已从 Graph 编译配置中移除——该选项需要配套的 `graph.update_state` 恢复逻辑，当前 chat 路由每次新消息都是全新的 `astream_events` 调用，保留该选项会导致 agent 节点永远不执行；用户中断依赖 Redis cancel flag 实现，不依赖 LangGraph interrupt 机制。

**`generate_image` 轮询内的中断**：使用 Redis cancel flag（key：`cancel:{session_id}:{run_id}`）。FastAPI 收到新用户消息时设置当前 `run_id` 的 cancel flag；`generate_image` 轮询每次 `asyncio.sleep(2)` 后检查 Redis，检测到后抛 `CancelledError` 提前退出。新一轮用户消息使用新的 `run_id`，避免上一轮取消信号误触发后续生成。

session_id 在整个对话窗口内不变；run_id 每轮 Agent 执行生成一次，用于取消、SSE 事件隔离和断线重连。当前 C-6.1 chat 路由中 `stream_id == run_id`，`turn_id` 临时传入 `session_id`；后续如果需要严格按用户消息追踪，应把 `turn_id` 改为消息 ID，并同步 `generate_image` 的 cancel key 取值。

---

## SSE 流式输出设计

### 事件协议

每个 SSE 事件格式：`event: <type>\ndata: <JSON>\nid: <递增ID>\n\n`

| 事件类型 | 触发时机 | data 结构 |
|----------|----------|-----------|
| `text_delta` | LLM token 流式输出；`agent_node` 当前优先通过 `_llm.astream` 直接推送模型原文到 SSE，其他节点仍可由 `on_chain_stream` 兜底 | `{"content": "..."}` |
| `tool_start` | Agent 开始调用工具 | `{"tool": "analyze_reference_image", "input": {...}}` |
| `tool_end` | 工具调用完成 | `{"tool": "...", "summary": "用户友好的一句话摘要"}` |
| `generation_start` | 图像生成任务提交 | `{"task_id": "xxx", "run_id": "..."}` |
| `generation_done` | 图像生成完成 | `{"task_id": "xxx", "image_url": "...", "run_id": "..."}` |
| `prompt_update` | `enhance_prompt` / `refine_prompt` 得到结构化 prompt 后 | `{"prompt": "...", "negative_prompt": "...", "source": "enhance_prompt \| refine_prompt"}` |
| `error` | 发生错误 | `{"code": "GENERATION_TIMEOUT", "message": "..."}` |
| `done` | 本轮响应结束 | `{"finish_reason": "stop \| max_retries \| interrupted"}` |

`finish_reason` 三种值：
- `stop`：正常结束
- `max_retries`：达到重试上限，已返回最高分结果
- `interrupted`：用户中断当前循环

### 后端实现（`core/llm/streaming.py`）

从 LangGraph `astream_events` 过滤并映射到上述协议：

- `on_chat_model_stream` → `text_delta`
- `agent_node` 内部通过 `QueueEmitter.emit("text_delta", ...)` 直接透传 `_llm.astream` 产出的模型文本
- `on_chain_stream` 中提取到的 AIMessage → `text_delta` 兜底（适用于未走显式流式透传的节点）
- `on_tool_start` → `tool_start`
- `on_tool_end` → `tool_end`（原始输出经 `summarize_tool_output` 转为用户友好摘要）
- `generate_image` 工具内部完成后额外推送 `generation_start` / `generation_done`
- `enhance_prompt_node` / `refine_prompt_node` 得到结构化 prompt 后通过 `QueueEmitter` 推送 `prompt_update`

当前实现注意：`analyze_reference_image`、`search_similar_cases` 是 LangChain `@tool`，可产生 `tool_start/end`；`enhance_prompt`、`generate_image`、`evaluate_generated_image`、`refine_prompt` 当前由 Graph 节点直接调用，不保证出现 LangGraph tool event。前端必须以 `generation_start/done` 和文本事件为主，不应把所有工具状态都当作必达事件。

### 前端消费（`hooks/useSSE.ts`）

对话流拆成两步：

1. `POST /api/chat/sessions/{session_id}/messages` 提交用户消息，返回 `{"stream_id": "xxx"}`。
2. 前端用原生 `EventSource` 连接 `GET /api/chat/sessions/{session_id}/stream?stream_id=xxx` 消费 SSE。

按 `event` 字段分发：

- `text_delta`：追加到当前 AI 消息气泡
- `tool_start` / `tool_end`：消息气泡下方显示小状态条（"正在分析参考图..."），完成后自动收起
- `generation_start`：显示生成中占位卡片（loading 动画）
- `generation_done`：替换占位卡片为真实图片；中间对话区显示缩略图，右侧"生成图片"标签页加入可查看、批注、下载的图片项
- `prompt_update`：更新右侧工作区 `promptDraft` / `negativePromptDraft`，并切换到"提示词与参考图"标签页
- `error`：展示错误提示
- `done`：结束当前消息，根据 `finish_reason` 决定 UI 状态

### 前端三栏工作台设计

`/chat/[sessionId]` 是实际可用的图像生成对话工作台，不做营销式落地页。页面保持当前 Next.js 简约白色风格，采用左中右三栏布局：

| 区域 | 组件 | 职责 |
|------|------|------|
| 左侧 Sidebar | `AppSidebar` | 历史对话列表、知识库入口、返回首页 `/`、跳转 Dashboard、折叠/展开 |
| 中间对话区 | `ChatPanel` / `MessageList` / `InputBar` | 多轮对话、SSE 文本流、工具状态条、生成图缩略图、继续追问 |
| 右侧工作区 | `WorkspacePanel` | 标签页切换：提示词与参考图、生成图片 |

右侧工作区标签：

**提示词与参考图（`PromptReferenceTab`）**
- 顶部展示当前正向 prompt 和 negative prompt；Agent 生成或修正 prompt 后实时更新，用户也可以手动编辑。
- 支持上传 1 张 `control_image` 作为图生图结构底图，生成时优先保留建筑体量、透视关系、空间尺度和主要构图；底图不参与“最后一张参考图”推断。
- 支持上传多张 `reference_images` 作为语义参考，每张图必须选择参考意图：构图、色彩、建筑样式、材质、光线、环境、其他；可选填写补充说明。参考图继续走 VLM 分析并注入 Agent / Prompt，不作为默认图生图底图。
- 中部放置可滑动/可输入的量化参数，首批只纳入前端草稿：`temperature`、`lightingIntensity`、`stylization`、`materialStrength`、`compositionStrength`。
- 底部展示 `prompt_templates.py` 中已定义的风格模板，一键选择后写入 `selectedStyle` 并同步到下一轮消息。

**生成图片（`GeneratedImagesTab`）**
- 展示本会话所有 `generation_done` 返回的图片，支持大图预览。
- 提供下载按钮，优先使用浏览器下载远程图片；若跨域限制导致失败，后续补后端代理下载接口。
- 提供批注入口：首版用 Canvas 覆盖层支持画笔、撤销、清空、导出批注图；批注结果作为下一轮参考图上传或作为消息附件传给 Agent。
- 每张图保留"存入图库"按钮，调用 `POST /api/library/store`，不经过 Agent。

### 前端状态划分

| Store | 内容 | 来源 |
|-------|------|------|
| `chatStore` | messages、当前 sessionId、stream 状态、工具状态、生成中占位 | 会话 API + SSE |
| `workspaceStore` | sidebar 折叠、右侧标签、prompt 草稿、参考图草稿、参数滑块、选中风格、批注草稿 | 用户操作 + SSE `generation_done` / 后续 prompt 事件 |

当前 SSE 协议已支持 `prompt_update` 事件，用于右侧 prompt 实时稳定刷新；后续如需同步关键 `DesignState` 或参数，可继续补充 `state_patch`：

| 事件类型 | 触发时机 | data 结构 |
|----------|----------|-----------|
| `state_patch` | Agent 更新关键 `DesignState` 或参数时 | `{"design_state": {...}, "generation_params": {...}}` |

### 关键细节

**工具状态半透明展示**：`tool_start/end` 显示为消息下方的小状态条，不打断主对话流，完成后自动收起，用户可感知 Agent 行为但不被技术细节干扰。

**`generate_image` 的解耦处理**：该工具内部是 Celery 异步任务，对 Agent 暴露为同步接口（内部轮询）。当前实现由 `QueueEmitter` 在任务提交后推送 `generation_start`，Celery 完成后推 `generation_done`，避免前端长时间无响应；这两个事件不依赖 LangGraph `tool_start`。

**断线重连**：每个事件携带递增 `id`，前端 `EventSource` 断开重连时传 `Last-Event-ID`，后端按 `stream_id` 从断点续传。

---

## 图像生成平台统一接口设计

### 选型结论：httpx 统一 POST

三个平台 API 格式差异大，使用 httpx 异步客户端统一调用，配合抽象工厂模式封装差异。

| 平台 | Endpoint | 格式 | OpenAI 兼容 |
|------|----------|------|------------|
| 阿里云百炼（万相） | `POST /api/v1/services/aigc/text2image/image-synthesis` | 异步任务制（提交→轮询） | 否，DashScope 私有格式 |
| 火山引擎豆包 | `POST /api/v3/images/generations` | 类 OpenAI images 格式 | 部分兼容 |
| GrsAI | `POST /v1/draw/completions`（`https://grsai.dakka.com.cn`） | 同步返回，响应从 `results[0].url` 取图片 URL | 否，私有格式 |

### 抽象工厂结构

```
core/image/
├── base.py          # 抽象基类 ImageGeneratorBase + 统一数据结构
├── factory.py       # ImageGeneratorFactory，按 provider 名称实例化
├── generator.py     # 调度器，从 dashboard_config 读取当前平台后调用工厂
├── bailian_client.py
├── volcengine_client.py
└── grsai_client.py
```

**统一数据结构**

```python
@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str | None = None
    ref_image_url: str | None = None       # 兼容旧字段；新代码写入 control_image_url
    control_image_url: str | None = None   # 单张图生图结构底图
    input_image_urls: list[str] | None = None  # 图生图输入顺序：control_image 在前，annotated_image 在后
    width: int = 1344
    height: int = 768
    steps: int = 30
    seed: int | None = None
    aspectRatio: str | None = None
    imageSize: str | None = None

@dataclass
class GenerationResult:
    image_url: str
    provider: str
    generation_time: float
    raw_response: dict
```

**抽象基类**

```python
class ImageGeneratorBase(ABC):
    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        ...
```

**工厂**

```python
class ImageGeneratorFactory:
    _registry = {
        "bailian": BailianClient,
        "volcengine": VolcengineClient,
        "grsai": GrsaiClient,
    }

    @classmethod
    def create(cls, provider: str, api_key: str, model: str) -> ImageGeneratorBase:
        return cls._registry[provider](api_key=api_key, model=model)
```

### 三个客户端的核心差异

**百炼（`bailian_client.py`）**
异步任务制，两步：提交任务拿 `task_id` → 轮询 `/api/v1/tasks/{task_id}` 直到 `SUCCEEDED`。轮询逻辑封装在客户端内部，对外暴露同步接口。当前代码使用 DashScope image-generation endpoint，并从 `output.choices[0].message.content[0].image` 取图像 URL；图生图时仅将 `control_image_url` 按 `messages[].content[].image` 传入。

**豆包（`volcengine_client.py`）**
同步返回，直接 POST 拿结果，响应结构类似 OpenAI images API，从 `data[0].url` 取图片 URL。图生图时使用请求体 `image` 字段，仅传 `control_image_url`。

**GrsAI（`grsai_client.py`）**
同步返回，`gpt-image` 模型 POST 到 `https://grsai.dakka.com.cn/v1/draw/completions`，`nano-banana` 模型 POST 到 `/v1/draw/nano-banana`，响应从 `results[0].url` 取图片 URL。构造器接收 `model` 参数，根据模型名称自动选择 endpoint 和 payload 格式。图生图时使用请求体 `urls` 字段传 URL 列表，列表中只包含 `control_image_url`。

### 调度器

```python
# generator.py
class ImageGenerator:
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        config = await dashboard_service.get_config("image_provider")
        client = ImageGeneratorFactory.create(
            provider=config["provider"],
            api_key=config["api_key"],
            model=config["model"]
        )
        return await client.generate(request)
```

工具层（`agent/tools/image_generator.py`）只调用 `ImageGenerator.generate()`，平台差异完全封装在各客户端内。

---

## 对话 LLM 统一接口设计

### 平台范围

仅支持百炼（Qwen3-VL）和火山引擎豆包 VLM，Dashboard 可切换，不扩展其他平台。

| 平台 | 模型 | Endpoint | 格式 |
|------|------|----------|------|
| 阿里云百炼 | Qwen3-VL | `POST /compatible-mode/v1/chat/completions` | OpenAI 兼容格式，图片放 `content[].image_url` |
| 火山引擎豆包 | Doubao VLM | `POST /api/v3/chat/completions` | OpenAI 兼容格式，图片放 `content[].image_url` |

两个平台均兼容 OpenAI Chat Completions 格式，差异主要在 Endpoint 和 model 字段，封装在各客户端内。

### 抽象基类

```python
class LLMClientBase(ABC):
    @abstractmethod
    async def ainvoke(self, messages: list[BaseMessage]) -> str:
        """纯文本对话"""
        ...

    @abstractmethod
    async def ainvoke_with_vision(
        self,
        messages: list[BaseMessage],
        images: list[str]          # image_url 列表
    ) -> str:
        """带图片的视觉理解"""
        ...

    @abstractmethod
    async def astream(
        self,
        messages: list[BaseMessage],
        images: list[str] | None = None
    ) -> AsyncIterator[str]:
        """流式输出，streaming.py 通过此方法消费"""
        ...
```

### 工厂

```python
class LLMClientFactory:
    _registry = {
        "bailian": BailianLLMClient,
        "volcengine": VolcengineLLMClient,
    }

    @classmethod
    def create(cls, provider: str, model: str, api_key: str) -> LLMClientBase:
        return cls._registry[provider](model=model, api_key=api_key)
```

### 调度器（`core/llm/client.py`）

```python
class LLMClient:
    async def ainvoke(self, messages, images=None) -> str:
        config = await dashboard_service.get_config("llm")
        client = LLMClientFactory.create(
            provider=config["provider"],
            model=config["model"],
            api_key=config["api_key"]
        )
        if images:
            return await client.ainvoke_with_vision(messages, images)
        return await client.ainvoke(messages)
```

工具层和节点只调用 `LLMClient`，平台差异完全封装在各客户端内。

---

## Embedding 模块设计（image-rag-mcp）

文本和图像 embedding 接口分离，各自独立基类和工厂。

### 抽象基类

```python
class TextEmbeddingClientBase(ABC):
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...

    async def embed(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]


class ImageEmbeddingClientBase(ABC):
    @abstractmethod
    async def embed_image(self, image_url: str) -> list[float]:
        ...
```

### 火山引擎文本实现（`volcengine_text.py`）

- 模型：`doubao-embedding-vision-251215`（与图像复用同一跨模态模型，文本输入走同一 endpoint）
- 向量维度：2048
- 调用方式：httpx POST，多模态 endpoint（`https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`），input 使用 `{"type": "text", "text": "..."}`
- 认证：`Authorization: Bearer <api_key>`

### 火山引擎图像实现（`volcengine_image.py`）

- 模型：`doubao-embedding-vision-251215`
- 向量维度：2048（跨模态共享空间，文本与图像同维）
- 调用方式：httpx POST，多模态专用 endpoint（`https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`）
- 输入：图片 URL（`{"type": "image_url", "image_url": {"url": "..."}}`），本地文件需转 base64 data URL
- 认证：`Authorization: Bearer <api_key>`

### 工厂

```python
class TextEmbeddingFactory:
    _registry = {"volcengine": VolcengineTextEmbedding}

    @classmethod
    def create(cls, provider: str, api_key: str) -> TextEmbeddingClientBase:
        ...

class ImageEmbeddingFactory:
    _registry = {"volcengine": VolcengineImageEmbedding}

    @classmethod
    def create(cls, provider: str, api_key: str) -> ImageEmbeddingClientBase:
        ...
```

调用方按需选择工厂，文本和图像 embedding 完全解耦。

---

## 图像评估评分设计

### EvaluationResult 数据结构

```python
class EvaluationResult(TypedDict):
    score: float                    # 加权总分 0.0~1.0，低于 0.8 触发重试
    style_score: float              # 风格符合度
    material_score: float           # 材质还原度
    lighting_score: float           # 光线与氛围
    composition_score: float        # 构图与视角
    quality_score: float            # 整体质量（清晰度、无畸变）
    reference_score: float | None   # 参考图相似度，无参考图时为 None
    feedback: str                   # LLM 给出的一句话改进建议，供 refine_prompt 使用
```

### 评分维度与权重

**无参考图时**（`reference_images` 为空）：

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| 风格符合度 | 30% | 建筑风格是否与 `style` 描述一致 |
| 材质还原度 | 20% | 外立面材质（`facade_material`）是否可辨识 |
| 光线与氛围 | 20% | 光线时段、方向、氛围（`lighting`）是否匹配 |
| 构图与视角 | 15% | 视角（`viewpoint`）是否正确，构图是否合理 |
| 整体质量 | 15% | 图片清晰度、无明显畸变、无 AI 瑕疵 |

**有参考图时**（`reference_images` 非空）：

| 维度 | 权重 | 评估内容 |
|------|------|----------|
| 风格符合度 | 25% | 同上 |
| 材质还原度 | 15% | 同上 |
| 光线与氛围 | 15% | 同上 |
| 构图与视角 | 10% | 同上 |
| 整体质量 | 10% | 同上 |
| 参考图相似度 | 25% | 生成图与参考图在构图、色调、风格上的整体相似程度 |

> **当前实现（C-5）**：参考图相似度为整体综合评分，VLM 同时看生成图和所有参考图，给出一个整体相似度分。
>
> **待扩展（E 阶段）**：支持用户在上传参考图时标注参考意图（构图 / 色彩 / 建筑样式 / 材质 / 光线 / 环境 / 其他），存入 `ReferenceImageAnalysis.reference_intent` 字段。E-2 先保存意图并传给 Agent；评估时按意图动态调整 prompt（"这张图是构图参考，请只评估构图相似度"）、`reference_score` 拆分为多个子维度分数属于 E-4/E-5 后的评估增强，不阻塞参考图上传 UI。

### 工具签名

```python
async def evaluate_generated_image(
    image_url: str,
    design_state: DesignState,
    reference_images: list[ReferenceImageAnalysis]  # 空列表时不评估相似度维度
) -> EvaluationResult:
    ...
```

### refine_prompt 如何使用评分

`refine_prompt` 收到 `EvaluationResult` 后，根据各维度分数针对性修正：
- 材质分低 → 在 prompt 里强化材质描述
- 参考图相似度低 → 提取参考图 caption 中的关键特征加入 prompt
- 整体质量低 → 调整负向提示词（negative_prompt）

---

## 记忆系统设计

| 层次 | 内容 | 存储位置 | 生命周期 |
|------|------|----------|----------|
| 短期记忆 | 对话消息历史（最近 20 条） | PostgreSQL messages 表 | 会话内 |
| 工作记忆 | DesignState 结构化设计参数 | AgentState + sessions 表 JSON 字段 | 会话内，持久化 |
| 参考图记忆 | 上传图片 + LLM 分析结果 | reference_images 表 | 会话内 |
| 长期记忆（未来扩展） | 用户风格偏好、历史反馈 | user_preferences 表（当前未实现） | 跨会话 |

当前阶段不做用户登录系统，长期记忆不纳入当前数据库 schema；会话内记忆先由 `messages`、`sessions.design_state`、`reference_images` 和 LangGraph PostgreSQL checkpointer 承担。

---

## Langfuse 集成设计

### 追踪方式：`@observe` 显式装饰

每个节点函数和工具函数都加 `@observe()`，追踪粒度到函数级别。当前项目使用 Langfuse 4.x 顶层 API，并通过 `core/observability.py` 封装配置、no-op fallback 和输入输出更新。

**入口 Trace**：每轮用户消息在 `chat.py` 路由处包一个最外层 Trace，内部所有被装饰的节点和工具自动成为子 Span。

```python
from core.observability import observe, start_observation, update_current_span

async def handle_message(session_id: str, message: str):
    with start_observation(
        name="agent:turn",
        as_type="agent",
        input=message,
        metadata={"session_id": session_id},
    ):
        await graph.ainvoke(...)
```

**Agent 节点**（当前只有一个 `agent` 决策节点；生成、评估、重试由确定性子流程节点控制）：

```python
@observe(name="node:agent")
async def agent_node(state: AgentState) -> AgentState:
    update_current_span(
        input=state["messages"][-1].content,
        metadata={"design_state": state["design_state"], "retry_count": state["retry_count"]}
    )
    result = await llm.ainvoke(...)
    update_current_span(output=result.content)
    return state
```

**工具函数**：

```python
@observe(name="tool:enhance_prompt")
async def enhance_prompt(design_state: DesignState, ...) -> EnhancedPrompt:
    ...
```

**Trace 结构**：

```
Trace: agent:turn  (session_id, user_id)
  ├── Span: node:agent
  ├── Span: tool:analyze_reference_image（按需）
  ├── Span: tool:search_similar_cases（D-4 后按需）
  ├── Span: node:rag_gate
  ├── Span: node:enhance_prompt
  ├── Span: node:generate_image
  ├── Span: node:evaluate_image
  └── Span: node:refine_prompt（重试时出现，后接 generate_image）
```

### Prompt 本地管理：`agent/prompts.py`

Prompt 不存 Langfuse，统一放在 `agent/prompts.py`，用函数封装（方便传入变量），版本管理走 git。

| 函数名 | 用途 | 变量参数 |
|--------|------|----------|
| `agent_system()` | agent 节点 System Prompt，覆盖信息收集、工具选择、生成决策与重试控制；用户未选 `prompt_template` 时注入可用模板列表用于口头建议 | `design_state`, `reference_analysis`, `similar_cases`, `prompt_template` |
| `enhance_prompt_system()` | enhance_prompt 节点/函数指令；风格关键词仅来自用户选择的 `prompt_template` | `design_state`, `reference_analysis`, `similar_cases`, `prompt_template` |
| `evaluate_image_system()` | evaluate_generated_image 工具指令 | `design_state` |
| `refine_prompt_system()` | refine_prompt 节点/函数指令 | `original_prompt`, `evaluation_result` |
| `analyze_image_system()` | analyze_reference_image 工具指令 | 无（固定） |

Prompt 修改通过 git commit 记录，回滚用 `git revert`，无需外部依赖。

---

## Agent 与 image-rag-mcp 通信机制

使用 `langchain-mcp-adapters` 库，将 FastMCP stdio 服务自动适配为 LangChain Tool，Agent 无感知底层通信细节。

```python
# backend/agent/graph.py（Agent 初始化时）
from langchain_mcp_adapters.client import MultiServerMCPClient

mcp_client = MultiServerMCPClient({
    "image-rag": {
        "command": "python",
        "args": ["image-rag-mcp/server.py"],  # D-1 新增；当前 image-rag-mcp/main.py 只是 uv 占位入口
        "transport": "stdio"
    }
})
mcp_tools = await mcp_client.get_tools()  # 自动转为 LangChain Tool
mcp_tools = [
    tool for tool in mcp_tools
    if tool.name in {"search_by_text", "search_by_image", "get_image_by_id"}
]
# 与本地工具合并后传给 Agent；store_generated_image 不暴露给 Agent
all_tools = local_tools + mcp_tools
```

MCP 进程由 `MultiServerMCPClient` 管理生命周期，FastAPI 启动时初始化，关闭时自动终止。`store_generated_image` 只允许 `POST /api/library/store` 后端接口直接调用，不加入 Agent 工具列表，避免 Agent 在对话中误触发存储。

当前实现状态：`image-rag-mcp` 已完成 embedding 客户端；`server.py`、`tools/`、`core/vlm_caption.py`、`core/milvus_client.py`、`core/pg_client.py` 尚未创建，`backend/agent/tools/search_library.py` 仍是返回空列表的 stub。D-1 ~ D-4 负责补齐 MCP 服务和 Agent 侧接入。

---

## 图像生成任务流转（Celery）

### 状态存储

Celery result backend 使用 Redis，`task_id` 存入 `AgentState.current_task_id`，工具内部轮询 Redis 直到任务完成。用户取消信号也存 Redis，key 为 `cancel:{session_id}:{run_id}`。

### `generate_image` 工具内部流程

```python
# 1. 提交 Celery 任务，立即通过 SSEEmitter 推送 generation_start 事件
task = generate_image_task.delay(request)
yield emitter.emit("generation_start", {"task_id": task.id, "run_id": run_id})

# 2. 轮询 Redis，每 2s 检查一次，最多等 120s；同时检查 cancel flag
cancel_key = f"cancel:{session_id}:{run_id}"
for _ in range(60):
    await asyncio.sleep(2)
    if await redis.exists(cancel_key):
        raise CancelledError("interrupted by user")
    result = AsyncResult(task.id)
    if result.ready():
        gen_result = result.get()
        yield emitter.emit("generation_done", {...})
        return gen_result

# 3. 超时处理：generate_image 抛 TimeoutError；generate_image_node 计入 retry_count
raise TimeoutError("generation timeout")
```

超时后进入确定性生成子流程的重试分支（受 `retry_count < 3` 约束），不是交给 Agent 自由决定。

用户中断（`CancelledError`）不计入 `retry_count`，Agent 直接回复用户"已中断"并等待下一条消息。

当前实现差异：`AgentState.current_task_id` 字段已保留，但 `generate_image_node` 尚未把 Celery `task.id` 写回 state；如前端需要展示或查询当前任务 ID，需在后续实现中补齐。

---

## Control Image 与参考图上传流程

### 设计原则

- `control_image` 是图生图结构底图，v1 只允许 1 张。它用于约束建筑形态、体量、透视、尺度、空间关系和主要构图。
- `reference_images` 是语义参考图，允许多张。它们继续通过 VLM 分析后注入 `agent_node`、prompt 构建和结果评估，用于风格、材质、光线、色彩、环境等参考。
- 不再从 `reference_images` 中自动取最后一张作为图生图底图；用户必须在前端显式上传或替换 `control_image`。

### 存储策略

通过 `storage_service` 抽象屏蔽环境差异：

| 环境 | 用户上传 | 系统生成图（本地化） | URL 格式 |
|------|----------|---------------------|----------|
| 本地开发 | `backend/uploads/` | `backend/generated/` | `http://localhost:8000/static/uploads/{uuid}.ext` / `http://localhost:8000/static/generated/{uuid}.ext` |
| 生产目标 | MinIO bucket（uploads） | MinIO bucket（generated） | `http://minio:9000/{bucket}/{uuid}.ext` |

切换目标通过环境变量 `STORAGE=local|minio` 控制。当前已实现 `local` 分支，`minio` 分支暂抛 `NotImplementedError`，后续业务上传文件仍需补齐 MinIO 支持。

系统生成图不再直接使用云端 provider 返回的临时 URL：Celery worker 在 `tasks/image_task.py` 里拿到结果后立即调用 `storage_service.download_and_save_generated_image()`，把图片下载并保存到 `backend/generated/`，写回 `/static/generated/{uuid}.ext`，避免云端 URL 过期导致历史会话图片失效。用户上传（参考图、批注图）和系统生成图的目录在本地开发按语义分开，不混用。

### 上传接口响应

```json
// POST /api/upload 响应
{
  "file_id": "uuid",
  "url": "/static/uploads/xxx.jpg"
}
```

前端拿到 `url` 用于预览，同时在右侧工作区为该图片选择参考意图。下一条消息或生成请求需把图片信息一起传给 Agent：

```json
{
  "content": "参考这几张图，生成一个现代极简别墅效果图",
  "control_image": {
    "file_id": "uuid",
    "url": "/static/uploads/base.jpg",
    "note": "保留原图建筑体量、低机位透视和庭院尺度"
  },
  "reference_images": [
    {
      "file_id": "uuid",
      "url": "/static/uploads/xxx.jpg",
      "intent": "composition",
      "note": "主要参考低机位人视构图"
    }
  ],
  "workspace": {
    "prompt": "...",
    "negative_prompt": "...",
    "generation_params": {
      "lightingIntensity": 0.7,
      "stylization": 0.5
    },
    "selectedStyle": "modern_minimal"
  }
}
```

Agent 收到后将 `control_image` 存入 `AgentState.control_image`，生成节点将其写入 `GenerationRequest.control_image_url`；同时将 `reference_images` 的 `url`、`intent`、`note` 存入 `AgentState.reference_images`，并调用 `analyze_reference_image(image_url=url)` 进行视觉分析。C-5 当前评估仍使用整体参考图相似度；按参考意图动态调整评估权重属于后续扩展。

当前实现状态：`POST /api/upload` 返回 `{file_id, url}`；`POST /api/chat/sessions/{session_id}/messages` 已支持 `control_image` / `reference_images` / `workspace` payload，并同步更新 Agent 状态。`sessions.workspace_state` 是结构化 prompt 草稿的服务端主存储；已发送参考图写入 PostgreSQL `reference_images.analysis`，其中保存 VLM 分析、用户 `intent/note`、`reference_intent/intent_note`、发送状态等；前端 `localStorage` 只作为未同步草稿和同浏览器 UI 恢复兜底。`control_image` 当前仍按 sessionId 存前端草稿，随下一条消息提交给 Agent。

注意：早期参考图记录可能只含 `analysis.intent` / `analysis.note`，分析完成后的记录会补充 `reference_intent` / `intent_note`。前端恢复历史会话时应兼容两组字段，避免旧记录或未完成分析的记录恢复为默认参考意图。

---

## API 接口

```
POST   /api/sessions                              创建会话
GET    /api/sessions                              获取会话列表
GET    /api/sessions/{session_id}                 获取会话详情
DELETE /api/sessions/{session_id}                 删除会话（级联删除 messages / reference_images / generation_tasks）
POST   /api/chat/sessions/{session_id}/messages   发送消息，返回 stream_id（E 阶段扩展 reference_images / workspace payload）
GET    /api/chat/sessions/{session_id}/stream     建立 SSE 流（query: stream_id）
POST   /api/upload                                上传参考图
GET    /api/styles/templates                      获取后端风格模板（来自 prompt_templates.py）
POST   /api/library/store                         规划：存入图库（D/E 阶段，前端按钮触发，后端直接调用 MCP）
POST   /api/generation/tasks                      规划：独立触发图像生成（当前主链路由 Agent SSE + Celery 完成）
GET    /api/generation/tasks/{task_id}/status     规划：查询独立生成任务状态
GET    /api/generation/sessions/{id}/results      规划：获取生成结果列表
POST   /api/annotations                           规划：保存生成图批注（E-4 后续，可选；首版可仅前端导出后作为上传图处理）
GET    /api/dashboard/config                      获取当前配置
PUT    /api/dashboard/config                      保存配置（模型、API Key 等）
GET    /api/dashboard/providers                   获取支持的图像生成平台列表
```

当前已实现路由：`/health`、`/api/sessions`（POST/GET）、`/api/sessions/{session_id}`（GET/DELETE）、`/api/chat/sessions/{session_id}/messages`、`/api/chat/sessions/{session_id}/stream`、`/api/upload`、`/api/styles/templates`、`/api/dashboard/config`、`/api/dashboard/providers`。`library`、`generation`、`annotations` 相关路由仍是规划项，不能作为当前联调入口。

---

## 数据库表结构

```sql
-- 主业务库（PostgreSQL）
sessions          (id, title, design_state JSON, workspace_state JSON, created_at)
messages          (id, session_id, role, content, created_at)
reference_images  (id, session_id, file_id, url, analysis JSON)
generation_tasks  (id, session_id, task_id, prompt, negative_prompt, provider, image_url, status, score, raw_response JSON, created_at)
-- LangGraph checkpointer 表由 langgraph-checkpoint-postgres 自动创建
-- Dashboard 配置不存 DB，改用 backend/config/dashboard.yaml（见下方说明）

-- 图库库（PostgreSQL，image-rag-mcp 使用）
image_library (
    id              UUID PRIMARY KEY,   -- 与 Milvus 向量的关联键
    session_id      UUID,
    image_url       TEXT,               -- 短 URL `/static/library/{id}.{ext}`，指向 image-rag-mcp/library_images 本地副本
    caption         TEXT,               -- VLM 生成的图片描述
    prompt          TEXT,               -- 正向提示词
    negative_prompt TEXT,
    design_state    JSON,               -- 完整设计参数
    provider        TEXT,               -- 生成平台
    created_at      TIMESTAMP
)
```

> ⚠️ `image_url` 不是任意外部 URL：D-3 副本管理改造后，store 工具一定会先把源图下载到 `image-rag-mcp/library_images/{id}.{ext}`，PG 与 Milvus 都存指向该副本的短 URL。这样图库与上游 `backend/generated/` 或 MinIO 生命周期完全解耦；前端需要 backend FastAPI 把 `image-rag-mcp/library_images/` 挂为 `/static/library` 静态目录才能直接展示。

当前实现状态：四张主业务表已由 SQLAlchemy 定义并在 FastAPI lifespan 中自动创建；`messages` 已用于 Chat/SSE 主链路；`sessions.workspace_state` 已作为 prompt 草稿主存储；`reference_images.analysis` 已保存参考图分析、用户意图/说明和 `sent` 状态；`generation_tasks` 已保存生成任务 `task_id`、prompt、negative prompt、provider、status、score、raw_response 等，用于历史会话恢复生成结果。旧开发库的 `sessions.title` / `sessions.workspace_state` 和 `generation_tasks` 扩展列由 `models/schema_guard.py` 在启动期补齐。

**Milvus Collection（向量库）**
```
image_id        # 主键，对应 image_library.id
caption_vector  # doubao-embedding-vision 生成（caption 文本输入，文字检索用），2048 维
image_vector   # doubao-embedding-vision 生成（图片输入，以图搜图用），2048 维
style           # 标量过滤字段
building_type   # 标量过滤字段
image_url       # 短 URL `/static/library/{id}.{ext}`，与 image_library.image_url 同源；标量字段，直接返回预览
```

---

## Dashboard 配置文件

配置存储在 `backend/config/dashboard.yaml`，不入数据库。Dashboard 页面读写此文件，`dashboard_service.py` 封装读写逻辑。

```yaml
# backend/config/dashboard.yaml（含 API Key，已加入 .gitignore）
llm:
  provider: bailian        # bailian | volcengine
  model: qwen-vl-max
  api_key: sk-xxx

image_provider:
  provider: bailian        # bailian | volcengine | grsai
  model: wanx2.1-t2i-turbo
  api_key: sk-xxx

embedding:
  provider: volcengine     # 目前仅支持 volcengine
  api_key: sk-xxx          # 火山方舟 API Key

langfuse:
  host: http://localhost:3000
  public_key: pk-xxx
  secret_key: sk-xxx
```

`backend/config/dashboard.yaml.example` 作为模板提交到 git，实际配置文件加入 `.gitignore`。

当前实现状态：C-8 已完成 Dashboard 配置漂移修正。后端 provider 列表与图像生成工厂对齐为 `bailian / volcengine / grsai`；Dashboard 配置已包含 `embedding` 配置块；前端类型与 UI 已支持 `image_provider.model` 和图像模型选择；`backend/config/dashboard.yaml.example` 已补齐 `embedding` 模板。

---

## Docker Compose 服务组成

开发环境基础服务：

```yaml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: aigc_agent
      POSTGRES_PASSWORD: postgres

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  etcd:
    image: quay.io/coreos/etcd:v3.5.18

  minio:
    image: minio/minio:RELEASE.2023-03-20T20-16-18Z
    ports: ["9001:9001"]

  milvus:
    image: milvusdb/milvus:v2.6.15
    ports: ["19530:19530", "9091:9091"]
    depends_on: [etcd, minio]

  langfuse-redis:
    image: redis:7-alpine

  langfuse-clickhouse:
    image: clickhouse/clickhouse-server:24.8

  langfuse-minio:
    image: minio/minio:RELEASE.2024-12-18T13-15-44Z

  langfuse-worker:
    image: langfuse/langfuse-worker:3
    depends_on: [postgres, langfuse-redis, langfuse-clickhouse, langfuse-minio]
    healthcheck: /api/health

  langfuse:
    image: langfuse/langfuse:3
    ports: ["3000:3000"]
    depends_on: [postgres, langfuse-redis, langfuse-clickhouse, langfuse-minio, langfuse-worker]
    healthcheck: /api/public/health
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/aigc_langfuse

  attu:
    image: zilliz/attu:v2.5
    ports: ["8080:3000"]
    depends_on: [milvus]
```

启动顺序：postgres、redis、etcd、minio → milvus；同时为 Langfuse 3.x 启动专用的 `langfuse-redis` / `langfuse-clickhouse` / `langfuse-minio` / `langfuse-worker` → `langfuse`、attu。

`langfuse-minio-init` 是一次性 bucket 初始化容器，执行成功后显示 `Exited` 属于正常状态。`langfuse` / `langfuse-worker` 已配置 healthcheck；如果只显示 `Started`，先等 10-30 秒或查看 `docker compose ps` / `docker compose logs langfuse langfuse-worker`。

Langfuse 3.x 要求 `ENCRYPTION_KEY` 是 64 个十六进制字符（256 bit）。本地 compose 使用固定开发值；生产或共享环境必须用 `openssl rand -hex 32` 生成后替换，并保持 web / worker 两个容器一致。

注意：后端当前使用 `langfuse>=4.5.1` Python SDK。该 SDK 对应 Langfuse 3.x 主线自托管架构；旧的 `langfuse/langfuse:2` 会因缺少新版 ingestion / OTEL 接口而在 export span batch 时返回 `404 Not Found`。因此本地 compose 已从 Langfuse v2 单容器升级为 Langfuse 3.x 及其依赖服务。

注意：compose 中的 MinIO 是 Milvus standalone 的对象存储依赖，不代表业务上传文件已支持 MinIO。业务文件存储当前默认使用本地 `backend/uploads/`；生产目标仍是补齐 `STORAGE=minio` 分支后切换到 MinIO。

注意：postgres 不再挂载 `init-db.sql` 到容器（WSL2 bind mount 路径不稳定）。首次全新部署（空 postgres_data volume）时需手动建库：
```bash
docker exec -it aigc_agent-postgres-1 psql -U postgres -c "CREATE DATABASE aigc_langfuse;"
docker exec -it aigc_agent-postgres-1 psql -U postgres -c "CREATE DATABASE aigc_image_library;"
```
现有部署（postgres_data 已有数据）`aigc_langfuse` 已在历史初始化时建好；`aigc_image_library` 已于 2026-05-11 手动创建完毕。

---

## RAG 候选浮窗与 rag_image 第三槽位（D-4 设计）

> 旧设计（"自动注入 prompt 的 similar_cases"）已于 D-4 整章替换。`AgentState.similar_cases` / `last_search_signature` / `make_search_signature` / `signature_changed` / `agent/tools/search_library.py::search_similar_cases` 全部废弃；`agent_system` / `enhance_prompt_system` / `refine_prompt_system` 中的 `similar_cases` 引用、`enhance_prompt` 函数签名的 `similar_cases` 参数也一并删除。

### 流程

每次进入生成子流程都先经过 `rag_gate_node`：

1. `rag_gate_node` 调用 MCP `search_by_text`（query 由 `building_type` / `style` / `facade_material` 拼接，标量过滤用 `building_type` / `style` 非空值），拿到候选列表。
2. 通过 `QueueEmitter` 推送 `rag_candidates` SSE 事件，前端在中栏对话渲染候选浮窗。
3. 节点开始 Redis 长轮询：1s 一次，最多 600s（`RAG_BLOCKING_TIMEOUT=600`）。轮询同时检查：
   - **pick key** `rag_pick:{session_id}:{run_id}`：用户在浮窗点了候选或「跳过」，由 `POST /api/library/pick` 写入。值为 `image_id`（选中）或 sentinel（跳过，如空字符串或 `null`）。
   - **cancel key** `cancel:{session_id}:{run_id}`：用户在阻塞期间发了新消息，由 chat 路由设置；命中抛 `asyncio.CancelledError`，与 `generate_image` 一致。
4. 三种退出：
   - 选中 → state 临时写 `_picked_image_id`，进入 `enhance_prompt` 节点；下载副本 / VLM ambience / 组装 `rag_image` 在 generation 子流程执行（详见 D-4 commit 4）。
   - 跳过 → 不写 `rag_image`，正常进 `enhance_prompt`。
   - cancel → 与 `generate_image` 一致抛 `CancelledError`，新一轮 run 重新进入。
   - timeout（600s 兜底）→ 视同跳过，不写 `rag_image`。

### `rag_image` 与生成请求

选中候选后，generation 子流程做：

1. 通过 MCP `get_image_by_id` 拿原图短 URL（`/static/library/{id}.{ext}`）。
2. 调用 `POST /api/library/select` 把图片下载到 `backend/uploads/`，拿到 `{file_id, url}`。
3. 对该副本跑一次 VLM 分析得到 `ambience_note`（光线 / 色彩 / 氛围 2-3 句，**不写建筑要素**，避免 prompt 风格漂移）。
4. 写入 `AgentState.rag_image: RagImage`：

```python
class RagImage(TypedDict, total=False):
    file_id: str
    image_url: str
    source_image_id: str   # MCP image_library 表的 image_id
    ambience_note: str     # VLM 输出的氛围描述
    sent: bool             # 是否已注入过本轮生成请求
```

5. `generate_image` 拼装 `input_image_urls` 时按顺序追加：`[control, annotated, rag]`（按存在性过滤），并在 prompt 头部按实际位置追加"图N 为氛围参考：{ambience_note}"。`enhance_prompt` 不感知 `rag_image` 存在，避免 LLM 阶段改写图位顺序。
6. `evaluate_generated_image` **不传 `rag_image`**，避免氛围参考被算进相似度评分。

### 开发期 feature flag

Commit 3 引入 env `RAG_BLOCKING_ENABLED`（默认 false）：
- false：`rag_gate_node` 召回完直接返回，不推 SSE、不阻塞。便于 Commit 3 ~ Commit 5 期间继续联调主链路。
- true：走完整阻塞 + SSE + 浮窗流程。Commit 6 联调通过后默认改 true。

### 持久化

`rag_image` 跟 `control_image` / `annotated_image` 一并由 Commit 5 落到 `sessions.workspace_state` 的分层 JSON 中（详见下一节"持久化边界"更新）。删除会话时，`backend/uploads/` 下属于该 session 的 rag 副本一并清理。

---

## 测试策略

### 原则

写一个模块，同步写对应测试，不攒到最后补。测试文件放在 `backend/tests/`，镜像 `core/` 和 `services/` 的目录结构。

```
backend/tests/
├── core/
│   ├── llm/
│   │   ├── test_factory.py
│   │   └── test_client.py
│   └── image/
│       ├── test_factory.py
│       └── test_generator.py
├── services/
│   └── test_dashboard_service.py
└── agent/
    └── tools/
        ├── test_image_evaluator.py
        └── test_prompt_builder.py
```

### 适合写单元测试的模块

| 模块 | 测试重点 |
|------|----------|
| `core/llm/factory.py` | 工厂注册逻辑、未知 provider 抛异常 |
| `core/image/factory.py` | 同上 |
| `core/llm/client.py` | 有无图片时路由到正确方法 |
| `agent/tools/image_evaluator.py` | 评分加权计算、有无参考图时权重切换 |
| `agent/tools/prompt_builder.py` | similar_cases 为空时正常降级 |
| `services/dashboard_service.py` | YAML 读写、缺失 key 时的默认值处理 |

### 不写单元测试的模块

- **三个图像生成平台客户端**：依赖真实 API，mock 掉失去意义，靠手动联调
- **LangGraph Graph**：集成测试成本高，靠手动跑对话流程验证
- **SSE 流式输出**：端到端测试更合适，单元测试难以覆盖流式场景

当前补充验证：`backend/scripts/test_chat_sse_flow.py` 是服务级联调脚本，使用真实 Redis/Postgres + fake graph 覆盖 C-6.1 主链路，不归类为单元测试。

---

## 开发进度

---

### A 阶段：基础设施与项目骨架

> 目标：本地开发环境全部跑通，后端和前端项目可以启动，数据库连接正常。

**A-1 基础设施启动**

- [x] 编写 `docker-compose.yml`（postgres:16 / redis:7-alpine / etcd:v3.5.18 / minio / milvus:v2.4.17 / Langfuse 3.x 所需 web/worker/clickhouse/minio/redis / attu:v2.4）
- [x] 配置 Langfuse 环境变量（`DATABASE_URL` 指向 postgres，共用实例不同 database）
- [x] 验证基础服务全部健康启动（`docker compose up -d`）
- [x] 创建 `backend/config/dashboard.yaml.example` 模板文件

> ⚠️ 注意：当前 `docker-compose.yml` 使用 Milvus standalone 镜像，并显式配置 etcd 与 MinIO 作为 Milvus 依赖；这个 MinIO 暂不承载业务上传文件。

**A-2 后端项目初始化**

- [x] 创建 `backend/` 目录，初始化 Python 虚拟环境（uv），安装依赖（fastapi / uvicorn / sqlalchemy / asyncpg / langgraph / langchain-mcp-adapters / celery / redis / httpx / pyyaml / langfuse）
- [x] 编写 `backend/main.py`（FastAPI 应用入口，挂载路由，lifespan 自动建表）
- [x] 编写 `backend/config.py`（从环境变量读取 DB_URL / REDIS_URL 等，pydantic-settings）
- [x] 编写 `backend/models/database.py`（SQLAlchemy async engine + session）
- [x] 编写 `backend/models/schemas.py`（sessions / messages / reference_images / generation_tasks 表定义）
- [x] 启动验证：`/health` 返回 200，四张表自动创建成功

> ⚠️ 注意：SQLAlchemy 使用异步模式（`asyncpg` driver），engine 用 `create_async_engine`，session 用 `AsyncSession`。

**A-3 前端项目初始化**

- [x] 在 `frontend/` 下初始化 Next.js 项目（App Router / TypeScript / Tailwind CSS）
- [x] 安装依赖（shadcn/ui / zustand）
- [x] 创建基础路由：`/`（首页）、`/chat/[sessionId]`、`/dashboard`
- [x] 验证 `npm run dev` 正常启动

**A-4 Dashboard 配置模块**

- [x] 编写 `backend/services/dashboard_service.py`（读写 `backend/config/dashboard.yaml`，缺失 key 返回默认值）
- [x] 编写 `backend/api/routes/dashboard.py`（`GET /api/dashboard/config` / `PUT /api/dashboard/config` / `GET /api/dashboard/providers`）
- [x] 编写前端 `dashboard/page.tsx` + `ModelSelector` / `ImageProviderConfig` / `ApiKeyForm` 组件，调用 Dashboard API 保存配置

> 🧪 测试：`tests/services/test_dashboard_service.py`
> - YAML 正常读写
> - 缺失 key 时返回默认值，不抛异常
> - 写入后再读取值一致

---

### B 阶段：核心能力层

> 目标：LLM 客户端、图像生成客户端、Embedding 客户端全部可独立调用，不依赖 Agent。

**B-1 LLM 客户端**

- [x] 编写 `core/llm/base.py`（`LLMClientBase` 抽象基类，定义 `ainvoke` / `ainvoke_with_vision` / `astream` 三个方法）
- [x] 编写 `core/llm/bailian_client.py`（httpx 调用百炼 `/compatible-mode/v1/chat/completions`，图片放 `content[].image_url`）
- [x] 编写 `core/llm/volcengine_client.py`（httpx 调用豆包 `/api/v3/chat/completions`，格式同上）
- [x] 编写 `core/llm/factory.py`（`LLMClientFactory`，注册 bailian / volcengine）
- [x] 编写 `core/llm/client.py`（`LLMClient` 调度器，从 `dashboard_service` 读取配置，有图片时路由到 `ainvoke_with_vision`）

> ⚠️ 注意：两个平台的 `model` 字段名称不同，百炼用 `qwen-vl-max`，豆包用具体的 endpoint model id，需从 dashboard.yaml 的 `model` 字段读取，不要硬编码。

> 🧪 测试：`tests/core/llm/test_factory.py`
> - 注册的 provider 能正确实例化
> - 未知 provider 抛 `KeyError` 或自定义异常
>
> `tests/core/llm/test_client.py`
> - `images=None` 时调用 `ainvoke`
> - `images` 非空时调用 `ainvoke_with_vision`

**B-2 文件存储模块**

- [x] 编写 `backend/services/storage_service.py`（`STORAGE=local` 时写 `backend/uploads/`，返回 `/static/uploads/{uuid}.ext`；`STORAGE=minio` 暂抛 `NotImplementedError`，后续补齐 MinIO 上传）
- [x] 在 `main.py` 挂载 `/static` 静态文件目录（开发环境）
- [x] 编写 `backend/api/routes/upload.py`（`POST /api/upload`，返回 `{file_id, url}`）

> ⚠️ 注意：上传文件需校验 MIME 类型，只允许 `image/jpeg` / `image/png` / `image/webp`，防止上传非图片文件。

**B-3 图像生成客户端**

- [x] 编写 `core/image/base.py`（`ImageGeneratorBase` 抽象基类 + `GenerationRequest` / `GenerationResult` dataclass）
- [x] 编写 `core/image/factory.py`（`ImageGeneratorFactory`，注册 bailian / volcengine / grsai）
- [x] 编写 `core/image/bailian_client.py`（httpx，提交任务拿 `task_id` → 轮询 `/api/v1/tasks/{task_id}` 直到 `SUCCEEDED`，轮询间隔 3s，超时 120s，不做内部重试）
- [x] 编写 `core/image/volcengine_client.py`（httpx，同步返回，从 `data[0].url` 取图片 URL，不做内部重试）
- [x] 编写 `core/image/grsai_client.py`（httpx，同步返回，POST 到 `https://grsai.dakka.com.cn/v1/draw/completions`，从 `results[0].url` 取图片 URL，支持 `gpt-image` / `nano-banana` 模型，不做内部重试）
- [x] 编写 `core/image/generator.py`（`ImageGenerator` 调度器，从 dashboard.yaml 读取平台配置）

> ⚠️ 注意：三个客户端均不做内部重试，失败直接抛异常，由 Agent 的 `retry_count` 机制控制重试。百炼图像生成是异步任务制，轮询逻辑封装在客户端内部，对外暴露同步接口。GrsAI 工厂的 `create` 方法需额外传入 `model` 参数。

> 🧪 测试：`tests/core/image/test_factory.py`
> - 注册的 provider 能正确实例化
> - 未知 provider 抛异常

**B-4 Embedding 客户端（image-rag-mcp）**

- [x] 编写 `image-rag-mcp/core/embedding/base.py`（`TextEmbeddingClientBase` / `ImageEmbeddingClientBase`，定义 `embed_batch` / `embed_image` 抽象方法，`embed` 单条便捷方法）
- [x] 编写 `image-rag-mcp/core/embedding/volcengine_text.py`（httpx 调用火山方舟 doubao-embedding，OpenAI 兼容 endpoint `https://ark.cn-beijing.volces.com/api/v3/embeddings`，维度 2048）
- [x] 编写 `image-rag-mcp/core/embedding/volcengine_image.py`（httpx 调用火山方舟 doubao-embedding-vision-251215，multimodal endpoint `https://ark.cn-beijing.volces.com/api/v3/embeddings/multimodal`，维度 3072，输入图片 URL）
- [x] 编写 `image-rag-mcp/core/embedding/factory.py`（`TextEmbeddingFactory` 注册 volcengine；`ImageEmbeddingFactory` 注册 volcengine）

---

### C 阶段：Agent 核心

> 目标：Agent 可以完整跑通一轮对话 → 生成图片 → 评估 → 重试的完整流程。

**C-1 会话与消息 API**

- [x] 编写 `backend/services/session_service.py` / `message_service.py`（sessions / messages 表 CRUD）
- [x] 编写 `backend/api/routes/session.py`（`POST /api/sessions` / `GET /api/sessions/{id}`）

**C-2 Agent 状态与 Graph 骨架**

- [x] 编写 `backend/agent/state.py`（`AgentState` / `DesignState` / `ReferenceImageAnalysis` / `GenerationResult` / `EvaluationResult` / `ImageRecord` 全部类型定义，均使用 `TypedDict`）
- [x] 编写 `backend/agent/state_utils.py`（规则计算 `missing_fields` / `completeness`，生成 `last_search_signature`，重置当前生成任务运行态）
- [x] 编写 `backend/agent/checkpointer.py`（`AsyncPostgresSaver`，生命周期由 FastAPI lifespan `async with` 管理）
- [x] 编写 `backend/agent/graph.py` 骨架（`agent` 决策节点 + `rag_gate` + 确定性生成子流程，早期节点为 stub；当前已移除 `interrupt_before=["agent"]`，中断依赖 Redis cancel flag）
- [x] 验证空 Graph 可以正常导入，节点结构正确

> ⚠️ 注意：`langgraph-checkpoint-postgres` 需要在 FastAPI 启动时初始化（`lifespan` 事件），不能在请求时临时创建连接。

**C-3 信息收集工具**

- [x] 编写 `agent/prompts.py`（`agent_system` / `analyze_image_system` / `enhance_prompt_system` / `evaluate_image_system` / `refine_prompt_system` 全部 Prompt 函数，结构化指令风格；`lookup_style_system` 已于 2026-05-10 随 `lookup_style_keywords` 一并移除）
- [x] 编写 `agent/tools/prompt_templates.py`（9 种建筑风格关键词库，每种风格含 `positive` / `negative` / `mood` / `description` 四个字段；`description` 为 2-3 句风格说明，供 `enhance_prompt` LLM 参考；`positive`/`negative` 直接拼入图像生成 prompt）
- [x] 编写 `agent/tools/image_analysis.py`（`analyze_reference_image`：调用 `LLMClient.ainvoke_with_vision`，返回 `ReferenceImageAnalysis` dict）
- [x] ~~编写 `agent/tools/style_lookup.py`~~（2026-05-10 移除：风格关键词不再由 Agent 自动注入，仅通过用户在前端选择的 `prompt_template` 注入）
- [x] 编写 `agent/tools/search_library.py`（`search_similar_cases`：stub，D-4 接入 MCP）
- [x] 工具按规则显式挂入 Graph：`agent_node` 内按规则调用（有图片 URL → 分析图片）；`rag_gate_node` 按规则调用 `search_similar_cases`

**C-4 Prompt 构建与图像生成工具**

- [x] `agent/prompts.py` 已在 C-3 补充 `enhance_prompt_system` / `refine_prompt_system`
- [x] 编写 `agent/tools/prompt_builder.py`（`enhance_prompt` / `refine_prompt`，Pydantic `EnhancedPrompt` 校验，解析失败重试 1 次，仍失败走 fallback）
- [x] 配置 Celery（`backend/celery_app.py`，broker=Redis，result_backend=Redis，方案 A：asyncio.run 包装）
- [x] 编写 `tasks/image_task.py`（`generate_image_task`，内部调用 `ImageGenerator.generate()`）
- [x] 编写 `agent/tools/image_generator.py`（`generate_image`：提交 Celery 任务，asyncio 轮询 Redis result backend 与 `cancel:{session_id}:{run_id}`，超时抛 TimeoutError，取消抛 CancelledError；`SSEEmitter` 协议 + `NullEmitter` 占位，C-6 注入真实 emitter）
- [x] 将三个工具接入确定性生成子流程节点（`enhance_prompt_node` / `generate_image_node` / `refine_prompt_node`）
- [x] `AgentState` 新增 `_enhanced_prompt` / `_current_gen_result` 内部传递字段

> ⚠️ 当前实现差异：`AgentState.current_task_id` 字段已定义，但 `generate_image_node` 尚未写入 Celery `task.id`；SSE 的 `generation_start` 会返回 `task_id`，state 持久化里的 `current_task_id` 后续如需要查询任务状态再补齐。

> ⚠️ 注意：`generate_image` 工具内部是 async 轮询，需用 `asyncio.sleep` 而非 `time.sleep`，否则会阻塞 FastAPI 事件循环。

> 🧪 测试：`tests/agent/tools/test_prompt_builder.py`
> - `similar_cases=[]` 时 `enhance_prompt` 正常返回，不报错
> - `refine_prompt` 材质分低时输出包含材质相关关键词（可用 mock LLM）

**C-5 评估与重试工具**

- [x] `agent/prompts.py` 已在 C-3 补充 `evaluate_image_system`（区分有无参考图两套权重说明）
- [x] 编写 `agent/tools/image_evaluator.py`（`evaluate_generated_image`：VLM 输出各维度原始分，后端代码加权计算总分；`reference_images` 为空时用 5 维权重，非空时用 6 维权重；解析失败重试 1 次，仍失败走 fallback 中性分；补充 `if __name__ == "__main__"` 手动测试入口）
- [x] `evaluate_image_node` 替换 stub，接入真实评估；`best_generation_result` 跨重试追踪最高分
- [x] 重试逻辑：`route_after_evaluate` 中 `score < 0.8` 且 `retry_count < 3` 时走 `refine_prompt`，否则返回 `best_generation_result`

> 🧪 测试：`tests/agent/tools/test_image_evaluator.py`（9 个测试全部通过）
> - 无参考图时权重之和为 1.0，不含 `reference_score`
> - 有参考图时权重之和为 1.0，含 `reference_score`
> - 加权计算精度正确，分数 clamp 到 [0, 1]

**C-6 SSE 流式输出**

- [x] 编写 `core/llm/streaming.py`（从 LangGraph `astream_events` 过滤，映射到 7 种 SSE 事件类型，`summarize_tool_output` 转用户友好摘要）
- [x] 编写 `backend/api/routes/chat.py`（`POST /api/chat/sessions/{id}/messages` 提交消息并返回 `stream_id`；`GET /api/chat/sessions/{id}/stream?stream_id=xxx` 返回 SSE，事件 id 递增，支持 `Last-Event-ID` 断线重连）
- [x] 加最外层 `agent:turn` Trace（Langfuse 4.x 使用 `start_as_current_observation`，由 `core/observability.py` 封装）

> ⚠️ 注意：原生 `EventSource` 只能发 GET 请求，因此消息提交和 SSE 订阅必须拆开。FastAPI SSE 响应需设置 `Content-Type: text/event-stream` 和 `Cache-Control: no-cache`，并在每个事件后 flush。断线重连时按 `stream_id` + `Last-Event-ID` 续传，需在内存或 Redis 中短暂缓存最近的事件序列（TTL 60s 即可）。

**C-6.1 后端 Chat/SSE 主链路硬化（E-1 前置）**

> 目标：在开始前端对话界面和 MCP 接入前，先保证后端纯文字对话链路稳定、可复现、可联调。

- [x] 修复消息重复注入风险：`POST /messages` 已入库最新用户消息后，`GET /stream` 构造 LangGraph 输入时不能再次 append 同一条用户消息
- [x] 补齐 AI 回复持久化：本轮 Agent 结束后，将最终 AI 文本写入 `messages` 表，保证刷新页面和下一轮历史一致
- [x] 确认并修正 `text_delta` 事件来源：当前 `agent_node` 使用封装后的 `_llm.ainvoke`，可能不会触发 LangGraph `on_chat_model_stream`；需保证 SSE 至少稳定输出文本增量或文本完成事件
- [x] 实现新消息中断旧 run：同一 `session_id` 收到新消息时，设置上一轮 `cancel:{session_id}:{run_id}` Redis flag，并记录当前 active run
- [x] 验证 `stream_id == run_id`、pending message、Redis event buffer、`Last-Event-ID` 断线重连的边界行为（`scripts/test_chat_sse_flow.py` 使用真实 Redis/Postgres + fake graph 验证）
- [x] 增加最小回归验证：纯文字对话一轮可完成，事件序列至少包含文本事件与 `done`，错误时返回 `error` + `done`（`scripts/test_chat_sse_flow.py` 覆盖成功路径；错误路径保留给后续 pytest/服务级测试扩展）

**C-7 Langfuse 集成**

- [x] 在 `backend/main.py` 初始化 Langfuse（从 dashboard.yaml 读取 host / public_key / secret_key；配置为空时显式禁用 tracing）
- [x] 关键工具函数加 `@observe()` 装饰（参考图分析、风格查询、RAG stub、prompt 构建/修正、图像生成、图像评估）
- [x] `agent` 节点函数加 `@observe(name="node:agent")`
- [x] 节点内用 `core.observability.update_current_span()` / `update_current_generation()` 关联 LLM 输入输出、中间状态、评分和 fallback 信息
- [ ] 验证 Langfuse UI 中能看到完整 Trace 树

**C-8 配置与文档漂移修正（D/E 前置）**

> 目标：先修正已发现的实现与文档不一致处，避免后续前端和 MCP 按错误配置继续扩展。

- [x] Dashboard 后端 provider 列表与图像生成实现对齐：移除残留 `openrouter`，补齐 `grsai` 及其模型选项
- [x] Dashboard 前端类型与 UI 补齐 `image_provider.model` 字段，允许用户选择图像生成模型
- [x] Dashboard 配置补齐 `embedding` 配置块的读写、默认值、示例文件与前端展示策略
- [x] 同步更新 `agent_graph.mmd`，从旧 ReAct 循环图改为当前 `agent` 决策节点 + `rag_gate` + 确定性生成/评估/重试子流程
- [x] 核对 `DEV_SPEC.md` 中目录结构与实际文件命名，特别是 `image-rag-mcp/server.py`、`tools/`、`core/pg_client.py`、`core/milvus_client.py`
- [x] 核对 SSE 文档与当前 C-6.1 实现：`text_delta` 可能是完整 AI 文本兜底；`generation_start/done` 来自 `QueueEmitter`，不是 LangGraph tool event
- [x] 明确当前未实现 REST 路由：`library`、`generation`、`annotations` 均为规划项，前端 E 阶段不能提前依赖

---

### D 阶段：image-rag-mcp 服务

> 目标：图库存储和检索功能完整可用，Agent 可以调用 MCP 工具存图和搜图。

**D-1 MCP 服务骨架与存储初始化**

- [x] 编写 `image-rag-mcp/config.py`（从环境变量读取连接配置，提供本地默认值；由 backend `MultiServerMCPClient` 的 `env` 字段注入）
- [x] 编写 `image-rag-mcp/server.py`（FastMCP stdio 入口，lifespan 初始化 PG pool 和 Milvus collection，注册工具，暴露 `health_check` 工具用于启动验证）
- [x] 编写 `image-rag-mcp/core/pg_client.py`（asyncpg pool，`init_schema` 建表，`insert` / `get_by_id` / `get_by_ids` CRUD；库名 `aigc_image_library` 独立于主业务库）
- [x] 编写 `image-rag-mcp/core/milvus_client.py`（pymilvus 封装，`init_collection` 建 Collection + HNSW 索引；`insert` / `search` 留给 D-3 实现；启动时幂等初始化）
- [x] 初始化 Milvus Collection（字段见下方 Schema，启动时自动建好）
- [x] 验证：`uv run python server.py` 能启动，PG 表和 Milvus Collection 自动建好，`health_check` 工具返回正常

**Milvus Collection Schema（image_library）**

```python
fields = [
    FieldSchema("image_id",        DataType.VARCHAR,      is_primary=True, auto_id=False, max_length=36),
    FieldSchema("caption",         DataType.VARCHAR,      max_length=2048),   # caption 冗余存储，检索时直接返回
    FieldSchema("caption_vector",  DataType.FLOAT_VECTOR, dim=2048),          # doubao-embedding-vision，caption 文本检索
    FieldSchema("image_vector",    DataType.FLOAT_VECTOR, dim=2048),          # doubao-embedding-vision，以图搜图
    FieldSchema("style",           DataType.VARCHAR,      max_length=128),    # 标量过滤
    FieldSchema("building_type",   DataType.VARCHAR,      max_length=128),    # 标量过滤
    FieldSchema("image_url",       DataType.VARCHAR,      max_length=1024),   # 仅返回，不过滤
]
# 向量索引：两个向量字段均用 HNSW + COSINE，M=16, efConstruction=200，搜索时 ef=64
# 标量索引：style / building_type 用 INVERTED 索引加速过滤；image_url 不建索引
```

**环境变量（image-rag-mcp/config.py）**

```
IMAGE_LIBRARY_PG_DSN       postgresql://postgres:postgres@localhost:5432/aigc_image_library
MILVUS_HOST                localhost
MILVUS_PORT                19530
DASHBOARD_YAML_PATH        ../backend/config/dashboard.yaml   # VLM / embedding 配置复用主服务
```

> ⚠️ 注意：`aigc_image_library` 是独立 PostgreSQL 库（方案 A），与主业务库 `aigc_agent` 分开，image-rag-mcp 和 backend 各自维护自己的连接。Milvus Collection 在 MCP 启动时幂等创建，不需要额外初始化脚本。

**D-2 VLM Caption 与向量化**

- [x] 编写 `image-rag-mcp/core/vlm_caption.py`（读取 dashboard.yaml 中的 LLM 配置，httpx 直调 VLM chat completions，生成 2-3 句检索用中文描述）
- [x] 调用 `TextEmbeddingFactory` 生成 caption 文本向量（2048 维），调用 `ImageEmbeddingFactory` 生成图片向量（2048 维，跨模态共享空间）

**D-3 MCP 工具实现**

- [x] 编写 `image-rag-mcp/tools/store.py`（`store_generated_image`：先把源图下载到 `library_images/{image_id}.{ext}` 副本，再用本地 data URL 跑 VLM caption + 双 embedding，最后插入 PG 和 Milvus；PG/Milvus 都存短 URL `/static/library/{id}.{ext}`，插入失败回滚副本；`style` / `building_type` 从 `design_state` 自动提取）
- [x] 编写 `image-rag-mcp/tools/search.py`（`search_by_text`：文字 → caption_vector 检索，支持可选 `filters: dict[str, str]` 标量过滤（只对非空字段构造 `expr`）；`search_by_image`：图片 → image_vector 检索，同样支持可选 filters；输入若是短库 URL 自动反解为本地文件 data URL；返回 Milvus 字段 image_id/caption/image_url/style/building_type/score）
- [x] 编写 `image-rag-mcp/tools/retrieve.py`（`get_image_by_id`：按 image_id 查 PostgreSQL）
- [x] 编写 `image-rag-mcp/core/storage.py`（图库副本管理：`save_source_url` 下载源 URL（http 或 data URL）到 `library_images/{image_id}.{ext}`，`library_url_for` 生成短 URL，`resolve_library_url` 反解短 URL 为本地 `Path`，`to_data_url` 把本地副本转 base64）
- [ ] backend FastAPI 挂 `/static/library` 静态目录，让前端能直接展示 RAG 召回的图（D-4 commit 1 一并落地）

**D-4 Agent 侧接入：RAG 候选浮窗与 rag_image 第三槽位**

> 拆 6 个 commit，每个 commit 可独立编译并独立验证。详见上方"RAG 候选浮窗与 rag_image 第三槽位（D-4 设计）"章节。

- [x] **Commit 1 — Backend static mount and library REST contract**
  - `backend/main.py` 挂 `/static/library` 静态目录，指向 `image-rag-mcp/library_images/`（D-3 遗留 TODO 一并解决）
  - FastAPI lifespan 初始化 `MultiServerMCPClient` 单例并挂 `app.state.mcp_client`；library_service 和后续 graph 节点都复用同一实例
  - `backend/services/library_service.py`：封装 MCP 调用，提供 `store_image / search_by_text / search_by_image / get_image_by_id`
  - `backend/api/routes/library.py`：`POST /api/library/store`（前端"存入图库"按钮）、`POST /api/library/select`（下载到 backend uploads 返 `{file_id, url}`）
  - 不接 Agent，独立 curl 验证
- [x] **Commit 2 — Wire MCP search into Agent and drop similar_cases**
  - 删除 `AgentState.similar_cases` / `last_search_signature`、`state_utils.py::make_search_signature` / `signature_changed`、`agent/tools/search_library.py::search_similar_cases`、`agent_system` / `enhance_prompt_system` / `refine_prompt_system` 中所有 `similar_cases` 引用、`enhance_prompt` / `_build_prompt_draft` / `_compose_llm_description` 函数签名中的 `similar_cases` 参数
  - 新增 `AgentState.rag_image: RagImage | None`、`AgentState.pending_rag_candidates`
  - 新增 `RagImage` TypedDict（file_id / image_url / source_image_id / ambience_note / sent）
  - `rag_gate_node` 调真实 MCP `search_by_text`，只把候选写进 state，**先不推 SSE、不阻塞**（commit 3 补）
  - 验证：纯文字对话正常完成；similar_cases 字段消失；rag_gate 调真实 MCP 不报错
- [ ] **Commit 3 — Emit rag_candidates SSE and block run for user pick**
  - `core/llm/streaming.py` 新增 `rag_candidates` SSE 事件类型
  - `rag_gate_node` 增强：召回后推 `rag_candidates`，然后 Redis 长轮询（1s 一次，最多 600s，env `RAG_BLOCKING_TIMEOUT=600`）
  - 轮询同时检 `rag_pick:{session_id}:{run_id}` 和 `cancel:{session_id}:{run_id}`；cancel 命中抛 `CancelledError`
  - 退出：选中 → state 写 `_picked_image_id`；skip（pick key value 为 sentinel）→ 不写 rag_image；timeout → 视同跳过
  - `backend/api/routes/library.py` 新增 `POST /api/library/pick`：写 Redis pending key（接收 `{image_id}`，skip 时 image_id 传 null）
  - chat.py 路由的新消息中断逻辑兼容：清掉 `rag_pick` key 与设置 cancel flag
  - 新增 env `RAG_BLOCKING_ENABLED`（默认 false）：false 时 rag_gate 不推 SSE、不阻塞，直接返回；联调通过后改 true
  - 验证：curl 触发对话进入 generation；SSE 流确认推了 rag_candidates；curl `POST /api/library/pick` 选中后 run 继续；不调 pick 则 600s 超时继续
- [ ] **Commit 4 — Inject rag_image as third slot in generation request**
  - 拿到 `_picked_image_id` 后调 MCP `get_image_by_id` 拿短 URL → `POST /api/library/select` 下载到 backend uploads 拿 `{file_id, url}` → 跑 VLM ambience 分析得到 `ambience_note`（光线/色彩/氛围 2-3 句，**不写建筑要素**）→ 写 `state["rag_image"]`
  - `agent/tools/image_generator.py` 拼装：`input_image_urls = [control, annotated, rag]`（按存在性过滤），prompt 头部按实际位置追加"图N 为氛围参考：{ambience_note}"，与现有"图1结构底图 / 图2批注图"逻辑统一
  - `evaluate_image_node` 不传 `rag_image` 给评估
  - 验证：手动构造 control + rag 请求，确认 provider 请求体里图片顺序正确、prompt 含"图N 为氛围参考"
- [ ] **Commit 5 — Refactor workspace_state and persist rag_image**
  - `sessions.workspace_state` JSON 重构为分层结构：`{prompt_draft, rag_image, control_image, annotated_image}`
  - `backend/services/session_service.py` 写入 / 恢复链路兼容新结构；`schema_guard.py` 处理旧记录（旧记录被读为整份 PromptDraft，自动迁移到 `prompt_draft` 子键下）
  - `GET /api/sessions/{id}` 返回新分层结构；前端 `workspaceStore` 同步消费
  - 顺带把 control_image / annotated_image 从前端 sessionId localStorage 迁到服务端持久化（D-4 顺手解决老问题）
  - 删除会话时清理 `backend/uploads/` 下该 session 的 rag 副本
  - 验证：选完候选 → 刷新页面 → workspace 里 rag_image / control / annotated 都还在；删会话 → uploads 里对应文件没了
- [ ] **Commit 6 — Add chat popup for RAG candidates with countdown**
  - 前端中栏对话区新增候选浮窗组件，消费 `rag_candidates` SSE
  - 浮窗内展示候选缩略图（用 `/static/library/{id}.{ext}` 短 URL）和倒计时（基于 `RAG_BLOCKING_TIMEOUT`）
  - 「选中」按钮调 `POST /api/library/pick` 传 image_id；「跳过」按钮传 null
  - 联调通过后把 `RAG_BLOCKING_ENABLED` 默认改 true
  - 端到端验证：存图 → 新会话生成 → 浮窗弹出 → 选中 → 生成图含氛围特征

---

### E 阶段：前端三栏工作台对接与联调

> 目标：前端从基础聊天页升级为图像生成对话工作台，完整走通用户对话 → 右侧提示词/参考图/参数协作 → 生成图片 → 批注反馈 → 下载/存入图库的全流程。

**E-1 三栏工作台骨架与纯文字对话**

- [x] 编写 `components/chat/ChatWorkspace.tsx`，落地左中右三栏布局，保持简约白色风格；桌面端三栏固定，窄屏时左/右侧栏可收起
- [x] 编写 `components/chat/AppSidebar.tsx`：历史对话列表、知识库入口、首页 `/` 跳转、Dashboard 跳转、折叠/展开
- [x] 编写 `components/chat/ChatPanel.tsx` / `MessageList.tsx` / `InputBar.tsx`
- [x] 编写 `hooks/useSSE.ts`：消费 `text_delta`、`tool_start/end`、`generation_start/done`、`error`、`done`
- [x] 编写 `store/chatStore.ts` 与 `store/workspaceStore.ts` 的最小状态
- [x] 验证纯文字对话流程正常，SSE 至少包含文本事件与 `done`

**E-2 右侧提示词与参考图工作区**

- [x] 编写 `components/workspace/WorkspacePanel.tsx`，提供"提示词与参考图"、"生成图片"两个标签页
- [x] 编写 `PromptReferenceTab.tsx`：顶部 prompt / negative prompt 展示与手动编辑
- [x] 增加单张 `control_image` 上传控件：作为图生图结构底图，独立于多张语义参考图；生成时不再自动取最后一张参考图作为底图
- [x] 编写参考图上传组件（内嵌于 `PromptReferenceTab`）+ 意图选择下拉：上传参考图后必须选择参考意图（构图 / 色彩 / 建筑样式 / 材质 / 光线 / 环境 / 其他）和可选说明
- [x] 扩展 `POST /api/chat/sessions/{session_id}/messages` 请求体，支持 `reference_images` 与 `workspace` payload
- [x] 扩展 `POST /api/chat/sessions/{session_id}/messages` 请求体，支持 `control_image` payload；后端写入 `AgentState.control_image`
- [x] 后端将 `intent` / `note` 预填入 `input_state["reference_images"]`，`agent_node` 分析后合并 intent/note
- [x] `ReferenceImageAnalysis` 新增 `reference_intent` / `intent_note` 字段
- [x] 参考图发送后标记 `sent: true`，保持显示在右侧，已发送的图禁止修改意图；下次发消息只发未发送的图
- [x] 参考图列表按 sessionId 存 localStorage，刷新/切换 session 后恢复，session 间相互隔离
- [x] 本地开发环境参考图转 base64 传给 VLM（`image_analysis.py` 的 `_to_data_url`），解决 VLM 无法访问 localhost URL 的问题；生产环境 MinIO 接入后图片有公网 URL，可直接传 URL
- [x] 验证 Agent 收到图片后触发 `analyze_reference_image`，并保留用户标注的参考意图
- [x] 图像生成层支持单张 `control_image_url`：百炼通过 `messages[].content[].image`，火山通过 `image` 字段，GrsAI 通过 `urls` 列表；`reference_images` 不进入 provider 请求体

**E-3 参数滑块、风格模板与 prompt 实时同步**

- [x] 后端 `agent_node` / `enhance_prompt_node` / `refine_prompt_node` 通过 `QueueEmitter` 推送结构化 `prompt_update` SSE 事件（含 `keywords`、`llm_description`、`custom_description`、`negative_prompt`、`source`）
- [x] 前端 `useSSE` 新增 `onPromptUpdate` 回调，消费结构化 `prompt_update` 事件，更新 `workspaceStore.promptDraft`
- [x] `SSEEventPayloadMap` / `SSEEventType` 补充 `prompt_update` 类型
- [ ] `GenerationControls.tsx` 暂缓：`temperature`、`lightingIntensity`、`stylization`、`materialStrength`、`compositionStrength` 不是百炼/火山/GrsAI 三家图像 API 的通用字段，后续如需真实参数控制再按 provider 能力单独设计
- [x] 从 `prompt_templates.py` 对齐前端风格模板数据源；后端新增 `GET /api/styles/templates` 输出模板，避免前后端手写两份长期漂移
- [x] 用户选择风格模板后写入 `workspaceStore.promptDraft.prompt_template`，按 `sessionId` 存 `localStorage`，并随下一条消息提交给 Agent
- [x] 验证：Agent 每轮对话后都会刷新右侧结构化 prompt 草稿；用户手动编辑 `custom_description` 和选择 `prompt_template` 后下一轮 Agent 能在上下文中读取

**E-3.5 会话工作区服务端持久化（E-4 前置）**

- [x] 新增后端 session workspace 持久化能力：建议 `sessions` 增加 `workspace_state JSON`（或等价表），保存 `keywords`、`llm_description`、`custom_description`、`negative_prompt`、`prompt_template`
- [x] 扩展 `GET /api/sessions/{session_id}` 返回 `workspace_state`，前端进入历史会话时优先用 PostgreSQL 恢复 prompt 草稿；`localStorage` 仅作为未同步兜底
- [x] 在 `POST /api/chat/sessions/{session_id}/messages` 接收 `workspace` payload 后同步写入 PostgreSQL，Agent SSE `prompt_update` 后也要持久化最新草稿，避免只存在浏览器
- [x] 将已上传/已发送参考图写入 `reference_images` 表，`analysis` JSON 保存 VLM 分析、`intent`、`note`、`sent` 等；前端参考图列表刷新后从后端恢复
- [x] 将生成任务/结果写入 PostgreSQL：保存 task_id、prompt、negative_prompt、image_url、provider、status、score、raw_response，供 E-4 生成图片区刷新后恢复
- [x] 明确删除会话时级联删除 workspace_state、reference_images、generation_tasks；保留 localStorage 清理作为前端辅助
- [x] 验证跨浏览器/清空 localStorage 后，历史消息、prompt 草稿、已发送参考图、生成图结果仍可按 session 恢复

**E-4 生成图片工作区、批注与下载**

- [x] 编写 `GeneratedImagesTab.tsx`：监听 `generation_done`，展示生成图片列表、大图预览、评分、重试次数
- [x] 中间对话区展示生成图缩略图，右侧生成图标签展示完整操作区
- [x] 实现下载按钮；跨域下载失败时记录问题，后续补后端代理下载接口
- [x] 编写 `ImageAnnotationCanvas.tsx`：画笔、撤销、清空、导出批注图
- [x] 批注图首版复用 `POST /api/upload`，作为 `annotated_image` 独立于普通 `reference_images` 随下一条消息发送给 Agent；独立 `POST /api/annotations` 可后续补
- [x] 生成完成后展示"存入图库"按钮；E-4 先做 UI 占位/禁用状态，待 D 阶段完成 `image-rag-mcp` 与 `POST /api/library/store` 后再接入真实调用。真实接入时后端直接调用 MCP `store_generated_image`，不经过 Agent

**E-5 全流程联调**

- [ ] 完整走通：创建会话 → 多轮对话 → 右侧编辑 prompt/参数/风格 → 上传带意图参考图 → 触发生成 → 评估重试 → 生成图展示 → 批注反馈 → 下载 → 存入图库
- [ ] 验证断线重连（关闭 SSE 连接后重新连接，从断点续传）
- [ ] 验证用户中断（生成中途发新消息，Agent 正确感知并重新决策）
- [ ] 验证刷新页面后消息历史、生成图历史和工作区关键状态可恢复；无法恢复的前端草稿需明确标注为临时状态

---

## 当前状态

**阶段**：A-1 ~ A-4、B-1 ~ B-4 已完成；C-1 ~ C-6 已初步完成；C-6.1 已完成代码硬化与 Redis/Postgres 集成验证；C-8 已完成 Dashboard 配置、前端类型/UI、`agent_graph.mmd` 和文档漂移修正；E-1 已完成三栏工作台骨架、纯文字对话与最小会话恢复；E-2 已完成参考图上传/意图/发送标记/payload 扩展/localStorage 临时持久化；E-3 已完成 prompt 实时同步与风格模板独立注入，参数滑块因缺少跨平台通用 API 字段暂缓；E-3.5 已完成会话工作区服务端持久化并通过跨浏览器恢复验证；E-4 已完成生成图片工作区、下载、批注图上传与批注图生图链路；E-5 过程中补齐了中栏图片按比例显示 + 按对话位置锚定、系统生成图下载至 `backend/generated/` 的本地持久化、风格模板去自动注入、SSE 正常关闭时的假性断开提示修复；D-1 已完成 image-rag-mcp 骨架，FastMCP stdio + lifespan 启动 PG/Milvus，`image_library` 表与 Collection（HNSW + INVERTED 索引）幂等创建，`health_check` 工具通过 stdio E2E 验证返回正常；D-2 已完成 VLM caption + 双向量端到端打通，统一为 2048 维（DEV_SPEC 原写 image 3072 维与实际不符，已修正）；D-3 已完成 MCP 工具（store_generated_image / search_by_text / search_by_image / get_image_by_id）并通过 stdio E2E 自查（text 检索命中、style 过滤正确、image 自查 score≈1.0、PG 全字段回填）。

**建议执行顺序（2026-05-08 调整）**：
1. ~~C-6.1~~、~~C-8~~、~~E-1~~：已完成。
2. ~~E-2~~：已完成参考图列表按 sessionId 存 localStorage，刷新/切换 session 后恢复。
3. ~~E-3~~：已完成 `prompt_update` SSE、结构化 prompt 草稿与风格模板 `prompt_template` 注入；参数滑块暂缓。
4. ~~E-3.5~~：已完成将 prompt 草稿、参考图会话状态、生成任务结果从 `localStorage` / 前端内存迁移到 PostgreSQL；这是 E-4 前置，避免生成图工作区做完后因刷新恢复能力返工。
5. ~~E-4~~：已完成生成图批注下载、禁用图库占位、批注图作为 `annotated_image` 回传；多图 provider 请求按 control image、annotated image 顺序构造。
6. E-5：全流程联调。
7. ~~D-1~~：image-rag-mcp 骨架、PG 建表、Milvus Collection 初始化已完成。
8. ~~D-2~~：VLM caption + caption/image 双向量打通；统一 2048 维。
9. ~~D-3~~：MCP 工具（store/search_by_text/search_by_image/get_image_by_id）已实现并通过 stdio E2E 测试。
10. **D-4（当前）**：Agent 侧接入 + rag_image 候选浮窗（含 VLM 氛围描述、阻塞等待、rag_image 第三槽位）。
11. C-7：Langfuse 可观测性集成；如联调排障需要，可提前执行。

**最近决策记录**：
- 2026-05-12：D-4 拆 6 个 commit 落地，每个 commit 独立可编译可验证。关键决策点（与用户对齐）：
  1. **MCP client 生命周期**：Commit 1 在 FastAPI lifespan 起 `MultiServerMCPClient` 单例并挂 `app.state.mcp_client`，library_service 与 Commit 2 graph 节点都复用同一实例，避免起两个 stdio 子进程。
  2. **rag_gate 等待策略**：长 timeout 600s（env `RAG_BLOCKING_TIMEOUT`） + 前端 skip 按钮兜底。120s 太短容易让用户错过候选；不设 timeout 又会留僵尸 run。10 分钟兜底兼顾两端。
  3. **rag_gate 检 cancel flag**：`rag_gate_node` 长轮询期间同时检 `cancel:{session_id}:{run_id}`，与 `generate_image` 一致。新消息进来能立即打断旧 run，不必等 600s。
  4. **Commit 3/4 拆分点**：`POST /api/library/pick` 只写 `image_id`（skip 时 null），不在 pick 时同步下载副本。Commit 3 验证范围只到"拿到 image_id"；Commit 4 才做 `get_image_by_id` → `/api/library/select` 下载 → VLM ambience → 写 rag_image。
  5. **开发期 feature flag**：Commit 3 引入 env `RAG_BLOCKING_ENABLED`（默认 false）。flag 关时 rag_gate 召回完直接返回，不推 SSE、不阻塞，便于 Commit 3 ~ Commit 5 期间继续联调主链路。Commit 6 联调通过后默认改 true。
  6. **rag_gate 触发策略**：每次进入生成子流程都弹浮窗，用户不想换就点 skip。`AgentState.similar_cases` / `last_search_signature` / `make_search_signature` / `signature_changed` / `search_library.py::search_similar_cases` 全删；`agent_system` / `enhance_prompt_system` / `refine_prompt_system` / `enhance_prompt` / `_build_prompt_draft` / `_compose_llm_description` 中的 `similar_cases` 引用一并清。
  7. **workspace_state 重构**：Commit 5 把 `sessions.workspace_state` 从扁平 PromptDraft 重构为分层 `{prompt_draft, rag_image, control_image, annotated_image}`。顺手把 control_image / annotated_image 从前端 sessionId localStorage 迁到服务端持久化（DEV_SPEC 老问题）。`schema_guard.py` 自动迁移旧记录到 `prompt_draft` 子键。
- 2026-05-11：D-3 收尾追加图库副本管理。新增 `image-rag-mcp/core/storage.py`：`save_source_url` 把任意来源（http URL 或 base64 data URL）的图片下载到 `image-rag-mcp/library_images/{image_id}.{ext}`，`library_url_for` 生成短 URL `/static/library/{id}.{ext}`，`resolve_library_url` 把这种短 URL 反解为本地 `Path`。`tools/store.py` 改造：先生成 image_id → 下载源图到本地副本 → 用本地 data URL 跑 caption / 双 embedding → PG/Milvus 都存短 URL；任一插入失败时回滚副本。`tools/search.py` 的 `search_by_image` 加入"短 URL → 本地路径 → data URL"的解析，避免火山方舟拿不到相对 `/static/...` 路径。`scripts/test_d3_stdio.py` 同步更新覆盖：store 后断言磁盘文件存在、搜索结果都是短 URL、`search_by_image` 用短 URL 自查 score≈1.0；cleanup 三件套（PG + Milvus + 本地文件）。`.gitignore` 增加 `image-rag-mcp/library_images/`。**遗留 TODO（D-4 一并处理）**：backend FastAPI 需要把 `image-rag-mcp/library_images/` 挂为 `/static/library` 静态目录，前端才能展示图库召回卡片；可在 `backend/main.py` 的 `app.mount("/static/library", ...)` 中处理，路径通过 `IMAGE_LIBRARY_DIR` 环境变量或 hardcoded 相对路径解析。
- 2026-05-11：D-3 完成 MCP 工具实现。`core/milvus_client.py` 补齐 `insert` / `search` 两个方法（`search` 支持 `caption_vector` / `image_vector` 两个向量字段，标量过滤仅对 `style` / `building_type` 非空值构造 `expr`，搜索 `ef=64`）；新增 `tools/store.py`（VLM caption → 双 embedding → PG.insert + Milvus.insert，`style` / `building_type` 从 `design_state` 自动提取）、`tools/search.py`（返回 Milvus 字段：image_id / caption / image_url / style / building_type / score，不 join PG）、`tools/retrieve.py`（按 id 查 PG）；`server.py` 注册 4 个新工具。`scripts/test_d3_stdio.py` 通过 stdio E2E 覆盖 store×2→search_by_text→style filter→search_by_image self-match→get_image_by_id→cleanup 全链路；发现 FastMCP 新版 list-返回只走 `structuredContent.result`（不再附 text block），测试 parser 已做兼容。**新设计决策（待 D-4 实现）**：RAG 召回的候选图不再自动注入 prompt，改为 `rag_gate_node` 在中栏对话弹候选浮窗（最多 120s 阻塞，超时默认不选），用户选中后生成图作为 `rag_image` 第三槽位参考图（跟 control_image / annotated_image 并列）；此时对候选图跑一次 VLM 氛围分析得到 "ambience_note"（光线/色彩/氛围为主，非建筑要素），在 `generate_image_node` 拼 prompt 时按"图3 为氛围参考：{note}"追加，enhance_prompt 不感知 rag_image 存在，从而保证图位顺序在 LLM 阶段不被改写；rag_image 不进入 `evaluate_generated_image` 参与评分；rag_image 与 control_image 一起持久化到 `sessions.workspace_state`；旧 `AgentState.similar_cases` 字段与 `agent/prompts.py` 中 `similar_cases` 引用将在 D-4 一并废弃，候选图走 `backend/uploads/` 本地保存（沿用 `storage_service.download_and_save` 通路，以后整体切 MinIO 时统一切）。
- 2026-05-11：D-2 完成 VLM caption + 双向量端到端。新增 `image-rag-mcp/core/vlm_caption.py`，复用 dashboard.yaml 的 LLM 配置（支持 bailian / volcengine），用 httpx 直调 chat completions（不依赖 backend 包，避免反向依赖），System Prompt 约束输出 2-3 句紧凑中文建筑描述。`scripts/test_d2_smoke.py` 用 `backend/generated/` 下真实生成图（base64 data URL）验证：caption→2048 维文本向量、image→2048 维图像向量。**重要修正**：实测 `doubao-embedding-vision-251215` 是跨模态共享 2048 维空间，文字与图像同维同空间（最大 2048，可降维 1024），并非 DEV_SPEC 原写的 "image 3072 维"。已同步修改 DEV_SPEC 中"火山引擎文本/图像 embedding 实现"与"Milvus Collection / Schema"两处维度描述，`image-rag-mcp/config.py` 中 `IMAGE_VECTOR_DIM` 从 3072 改为 2048，旧 Milvus collection 已 drop 并按 2048 × 2048 重建。境外图（如 Wikipedia）会被火山方舟下载失败，本地图片必须先转 data URL 再调 VLM / image embedding，跟 `agent/tools/image_analysis.py` 的 `_to_data_url` 一致。
- 2026-05-11：D-1 完成 image-rag-mcp 骨架。新增 `image-rag-mcp/config.py`（PG DSN / Milvus host:port / dashboard.yaml 路径，环境变量优先、本地默认值兜底）、`core/pg_client.py`（asyncpg pool，启动时幂等执行 `CREATE TABLE IF NOT EXISTS image_library` + `insert / get_by_id / get_by_ids / health_check`）、`core/milvus_client.py`（pymilvus 同步 API + `asyncio.to_thread`，幂等创建 Collection 与 HNSW/COSINE 向量索引、`style` / `building_type` INVERTED 标量索引；`insert / search` 留给 D-3）、`server.py`（FastMCP `lifespan` 串起 PG/Milvus 生命周期，注册 `health_check` 工具）。验证两路：直接调 `scripts/test_d1_smoke.py` 检查 schema 与索引；`scripts/test_d1_stdio.py` 通过官方 `mcp.client.stdio` 启动 server 子进程，`list_tools` 拿到 `health_check` 并调用返回 `{"pg": {"ok": true}, "milvus": {"name": "image_library", "indexes": [...]}}`。`insert` / `search` 尚未实现，留给 D-3 与 caption 链路一起做。
- 2026-05-11：Milvus 升级至 v2.6.15，Attu 升级至 v2.5；清理了 etcd `by-dev` 前缀（14 key）、minio `a-bucket`、`milvus_data` volume（原 v2.4 无业务数据，直接清干净）。移除 docker-compose.yml 中 postgres 的 `init-db.sql` bind mount（WSL2 路径不稳定），改为注释说明手动建库命令；`aigc_image_library` 库已手动创建完毕。pymilvus 客户端已是 2.6.12，与 server v2.6.15 兼容，不需要更新。Milvus v2.6 原生支持 BM25，为后续 hybrid 检索留路，当前 D 阶段仍只做文字向量检索 + 标量过滤。
- 2026-05-11：确定 image-rag-mcp D 阶段核心设计：PG 使用独立库 `aigc_image_library`（方案 A），连接配置通过环境变量传入；Milvus Collection 字段含 `image_id`（VARCHAR 36 主键）、`caption`（冗余存储，免回 PG）、`caption_vector`（2048 维）、`image_vector`（3072 维）、`style`/`building_type`（VARCHAR 128，INVERTED 索引）、`image_url`（VARCHAR 1024）；向量索引 HNSW + COSINE，M=16, efConstruction=200；Agent 侧 D-4 只调 `search_by_text` + 标量过滤，`search_by_image` 工具暴露但暂不接入 Agent，待观察效果后决定。
- 2026-05-10：E-5 联调过程中修复四类问题并合并到一次 commit（`50cdb7e`）。
  1. 中栏生成图展示：移除 `h-40 w-full object-cover` 固定尺寸，改为 `w-full h-auto` 按原始比例自适应；`GenerationPreview` 新增 `assistantMessageId`，实时生成时在 `chatStore.upsertGenerationPreview` 中绑定 `currentAssistantMessageId`，历史会话加载时按 `messages.created_at` 与 `generation_tasks.created_at` 做时间夹挤回填；`MessageList` 按关联 id 把图片渲染在对应 assistant 消息下，兜底保留末尾未关联渲染。后端 `message_id` 列暂不加，保持现状。
  2. 系统生成图持久化：云端 provider 返回的临时 URL 过期会导致历史会话图片失效。新增 `backend/generated/` 目录与 `STATIC /static/generated` 挂载；`storage_service.download_and_save_generated_image()` 在 Celery worker 拿到 provider URL 后立即下载到本地，`image_task._async_generate` 将本地路径写回 `image_url`。目录按语义与用户上传 `uploads/` 拆开；`save_generated_image_base64` 顺手迁到 `generated/`，但它目前仍是死代码。
  3. 风格关键词去自动注入：删除 `agent_node` 的 Rule 2 自动 `lookup_style_keywords`、`enhance_prompt` 内部 `get_style` 反查以及两段 `style_section` 注入；`_prompt_keywords` 不再产出 `style_positive/negative`；`STYLE_LIBRARY` 与 `list_styles()` 保留给 `/api/styles/templates` 和 `agent_system` 的"可用模板列表"使用；用户未选模板时 LLM 只能在 `reply` 中口头建议在右侧选择。`agent/tools/style_lookup.py`、`lookup_style_system` Prompt、`streaming.py` 中 `lookup_style_keywords` 的两条 summary 字符串全部删除。`design_state.style` 字段保留，仅作状态显示，不再触发自动注入。
  4. SSE "流式连接已中断" 假报：`EventSource.onerror` 在服务器正常关闭连接时也会触发，与真正的网络错误无法区分。`useSSE` 新增 `doneReceived` 标志，收到 `done` 后 `onerror` 静默忽略。同时修复 `MessageList` 生成图 404：`<img src>` 直接用相对路径 `/static/generated/...` 会被 Next.js dev server 拦截，改为和 `GeneratedImagesTab` 一致走 `resolveImageUrl()` 拼前端 `NEXT_PUBLIC_API_BASE_URL`。
- 2026-05-09：修复 E-4 联调时 Langfuse `Context error: No active span` 与 `tool:generate_image` 被标记 error 的问题。根因是 `agent:turn` observation 只包住了初始化元数据更新，进入异步 LangGraph / SSE 事件循环前已经退出，后续节点和工具没有 active span；同时 SSE consumer 关闭时 `stream_agent_events` 的 `finally` 会直接取消内部 graph task，可能打断正在轮询 Celery 的 `generate_image`，并引发 asyncpg 连接关闭时的 `CancelledError` 噪音。现调整为 `agent:turn` observation 覆盖整个 `stream_agent_events` 消费过程；普通 EventSource 断连不再直接取消 LangGraph 任务，真正用户中断仍通过 Redis cancel flag（新消息设置 `cancel:{session_id}:{run_id}`）生效。
- 2026-05-09：E-4 完成生成图片工作区与批注图生图链路。批注导出复用 `/api/upload`，前端将结果保存为 session 级 `annotated_image`，手动清空或替换，不因新生成自动失效；提交消息时 `annotated_image` 与 `control_image` 并列写入 AgentState，不进入普通 `reference_images`，避免触发语义参考图 VLM 分析。图像生成请求新增 `input_image_urls`，顺序固定为 `control_image` 在前、`annotated_image` 在后；同时保留 `control_image_url` / `ref_image_url` 兼容字段。百炼按 content 数组先图后文发送，火山 `image` 字段在多图时传数组，GrsAI `urls` 字段传数组；同时存在两张输入图时 prompt 前置说明“图1/图2”含义并追加批注说明。
- 2026-05-09：E-3.5 跨浏览器恢复已人工验证通过：换浏览器后可按 session 恢复历史消息和 prompt 草稿。E-4 先实现不依赖 D 阶段的生成图展示、下载、批注与批注图作为参考图回传；“存入图库”按钮在 E-4 仅做 UI 占位/禁用提示，待 D 阶段完成 `image-rag-mcp`、图库存储表和 `POST /api/library/store` 后再接入真实调用。接入时由后端路由直接调用 MCP `store_generated_image`，不经过 Agent。
- 2026-05-09：图生图输入从“取最后一张参考图”调整为“单 `control_image` + 多 `reference_images`”。`control_image` 是唯一结构底图，用于约束建筑体量、透视关系、空间尺度和主要构图，并且是唯一进入图像生成 provider API 的图片输入；`reference_images` 只作为语义参考，经 VLM 分析后注入 Agent / Prompt / 评估，不进入 provider 请求体。生成请求统一只传 `control_image_url`，百炼走 `messages[].content[].image`，火山走 `image` 字段，GrsAI 走 `urls=[control_image_url]`。
- 2026-05-09：修复前端 `localStorage` 恢复时序问题：`localStorage` 正常刷新不会清空；此前 `workspaceStore` 使用 Zustand `skipHydration: true`，但 `ChatWorkspace` 在 `rehydrate()` 完成前加载 session 并调用 `getPromptDraft(sessionId)`，会读到空的 `promptDraftBySession` 并把空草稿写回当前 session，表现为刷新后模板和已生成 prompt 消失。现改为等待 `useWorkspaceStore.persist.rehydrate()` 完成后再加载 session 并恢复 prompt 草稿，同时移除 `PromptReferenceTab` 内重复恢复逻辑，避免组件 mount 顺序互相覆盖。
- 2026-05-09：决定新增 E-3.5 作为 E-4 前置阶段：当前 `localStorage` 只能恢复同一浏览器的参考图和 prompt 草稿，不满足历史 session 的服务端恢复语义。E-3.5 目标是把会话业务状态迁移到 PostgreSQL：结构化 prompt 草稿存 `sessions.workspace_state` 或等价 JSON；参考图 `intent/note/sent/analysis` 存 `reference_images.analysis`；生成任务结果存 `generation_tasks` 或扩展表。`localStorage` 后续只保留布局偏好、未同步草稿兜底和临时 UI 状态。这个阶段应在 E-4 之前完成，因为 E-4 的生成图片工作区依赖生成结果刷新恢复能力，否则会返工。
- 2026-05-09：修复 E-3 prompt 草稿刷新丢失问题：此前只有参考图和 `prompt_template` 按 `sessionId` 持久化，完整结构化草稿仍是内存状态，关闭网页后 `keywords` / `llm_description` / `custom_description` / `negative_prompt` 会丢失。现调整 `workspaceStore`，新增 `promptDraftBySession` 并持久化到 `localStorage`；SSE `prompt_update`、用户编辑 `custom_description` / `negative_prompt`、重置草稿和风格模板选择都会同步写入对应 session。进入会话时从 `promptDraftBySession[sessionId]` 恢复整份 JSON 草稿，保持历史对话与右侧 prompt 状态一致。后端 Agent 状态仍为权威决策状态，本阶段不新增数据库 schema。
- 2026-05-09：E-3 后半完成风格模板独立注入：后端新增 `GET /api/styles/templates`，直接从 `prompt_templates.py` 暴露模板；前端右侧 Prompt 工作区新增风格模板下拉，选择后只写入结构化草稿的 `prompt_template` 字段，不覆盖 `keywords` / `llm_description` / `custom_description` / `negative_prompt`。`prompt_template` 按 `sessionId` 存 `localStorage`，随下一条消息通过 `workspace` payload 传给 Agent；`agent_system` / `enhance_prompt_system` 将其作为额外上下文使用，并明确不得覆盖用户已明确提供的字段。`prompt_update` SSE 继续保留当前模板，避免 Agent 刷新草稿时清空用户选择。参数滑块本阶段暂缓，原因是 `temperature` / `lightingIntensity` / `stylization` / `materialStrength` / `compositionStrength` 不是百炼、火山、GrsAI 三家图像生成 API 的通用字段；后续如需真实参数控制，应按 provider 能力单独设计。
- 2026-05-09：E-3.5 完成会话工作区服务端持久化：`sessions.workspace_state` 作为 prompt 草稿主存储，`reference_images.analysis` 保存参考图分析/意图/发送状态，`generation_tasks` 扩展保存 task_id、prompt、negative_prompt、provider、score、raw_response；`GET /api/sessions/{session_id}` 现在返回 workspace、reference_images、generation_tasks，前端进入历史会话时优先用 PostgreSQL 恢复，`localStorage` 只保留布局偏好和未同步草稿兜底。E-4 可以在此基础上继续做生成图片区刷新恢复。
- 2026-05-08：修复聊天工作台页面级滚动问题：`ChatWorkspace` 使用 `fixed inset-0` + `overflow-hidden` 固定为全视口工作台；中栏 `ChatPanel` 使用 `grid-rows-[72px_minmax(0,1fr)_auto]`，只有 `MessageList` 所在中间行独立滚动，输入栏始终固定在中栏底部；右栏 `WorkspacePanel` 固定高度并仅内容区域独立滚动，header 固定。
- 2026-05-08：修复偶发 `asyncpg InterfaceError: connection is closed`：后端 SQLAlchemy async engine 开启 `pool_pre_ping=True` 与 `pool_recycle=1800`，避免连接池复用被 PostgreSQL/Docker/网络关闭的旧连接。该问题发生在普通请求拿 session 查询时，根因属于连接池健康检查缺失，不在业务 service 层做散乱重试。
- 2026-05-08：修复 `agent_node` 自动决策生成图片的问题：新增后端显式生成意图硬规则，只检查最新用户消息，支持中文“生成 / 生成图片 / 开始生成 / 开始出图 / 出图 / 渲染”等和英文 `generate / render / create image` 等命令；“不要生成 / 先不生成 / 别出图 / do not generate”等否定表达优先拦截。`agent_node` 继续让 LLM 更新 `DesignState`，但最终 `ready_to_generate` 只由该硬规则决定，LLM 返回 `phase=generating` 且用户未明确生成时会被覆盖为 `collecting`。同步更新 `agent_system` 提示词，去掉“信息完整度够即可生成”的指令。
- 2026-05-08：E-3 prompt 实时同步第一段完成：后端 `enhance_prompt_node` / `refine_prompt_node` 在拿到结构化 `EnhancedPrompt` 后通过当前 SSE `QueueEmitter` 推送 `prompt_update`，前端 `SSEEventPayloadMap` / `useSSE` 增加 `prompt_update` 类型和 `onPromptUpdate` 回调，`ChatWorkspace` 收到事件后更新 `workspaceStore.promptDraft` / `negativePromptDraft` 并切回右侧 prompt 标签。参数滑块、风格模板和端到端人工验证仍保留在 E-3 后续项。
- 2026-05-08：Langfuse 部署升级策略调整为“SDK 4.x 对齐 Langfuse 3.x 主线”，而不是追求不存在的“server 4.x”。当前后端依赖是 `langfuse==4.5.1`，原 compose 使用 `langfuse/langfuse:2` 会在 span export 时返回 `404 Not Found`。现已将 `docker-compose.yml` 升级为 Langfuse 3.x 所需的 `langfuse` + `langfuse-worker` + `langfuse-clickhouse` + `langfuse-minio` + `langfuse-redis` 组合，并保留业务侧原有 `redis` / `minio` 供 Celery / Milvus 使用，避免基础设施相互污染。后续本地验证需执行 `docker compose up -d langfuse-redis langfuse-clickhouse langfuse-minio langfuse-minio-init langfuse-worker langfuse` 并重新生成 Langfuse project keys 填回 Dashboard。
- 2026-05-08：修复 Langfuse 3.x 启动失败：web / worker 日志报 `ENCRYPTION_KEY must be 256 bits, 64 string characters in hex format`，原因是 compose 中临时全 0 值未通过当前版本校验。已替换为 64 位 hex 开发值；生产环境需使用 `openssl rand -hex 32` 生成真实密钥，并保证 `langfuse` 与 `langfuse-worker` 使用同一个值。
- 2026-05-08：C-7 关键观测先落地，不等待完整 UI 联调：新增 `backend/core/observability.py` 统一封装 Langfuse 4.x 顶层 API（`observe`、`start_as_current_observation`、`update_current_span`、`update_current_generation`），FastAPI lifespan 从 Dashboard 配置初始化 Langfuse，配置为空时显式禁用 tracing；Chat SSE 每轮包 `agent:turn` 父观测，`agent` / `rag_gate` / `enhance_prompt` / `generate_image` / `evaluate_image` / `refine_prompt` 节点记录输入输出与路由状态，参考图分析、风格查询、RAG stub、prompt 构建/修正、图像生成、图像评估工具记录关键 LLM 原始输出、解析结果、fallback、评分和任务信息。C-7 仍保留“Langfuse UI 完整 Trace 树验证”未勾选，需填入真实 Langfuse key 后跑一轮对话确认。
- 2026-05-08：E-2 参考图持久化策略：参考图列表是前端草稿状态，不需要后端持久化；以 `sessionId` 为 key 存 `localStorage`，切换/刷新后恢复。已发送的图标记 `sent: true` 保持显示，用户手动删除才消失；下次发消息只发 `sent === false` 的图，避免重复提交给 Agent。
- 2026-05-08：E-2 已完成收尾实现：参考图上传、意图选择、`reference_images` / `workspace` payload、`ReferenceImageAnalysis.reference_intent` / `intent_note`、以及按 `sessionId` 的 `localStorage` 持久化均已落地；阶段下一步切换到 E-3 的 prompt 实时同步。
- 2026-05-09：E-3 结构化 prompt 草稿重构：把右侧 prompt 从字符串改成结构化 JSON 草稿，新增 `keywords` / `llm_description` / `custom_description` / `negative_prompt` 四个字段；`agent_node` 也会在每轮对话后主动刷新草稿，而不再只等生成阶段。`custom_description` 负责用户自由长描述，`llm_description` 负责模型整理出的描述性补全，最终生成提示词由同一份草稿组装。
- 2026-05-06：完成 `sessions.title` schema 漂移修复：当前后端 SQLAlchemy `Session` 模型、`create_session` 逻辑和前端会话列表均已依赖 `title` 字段，但 FastAPI 启动阶段使用的 `Base.metadata.create_all()` 只能创建缺失表，不能为已存在的 `sessions` 表自动补列，导致旧开发库在访问 `/chat/new` 时插入 `title` 失败。现已在 `backend/models/schema_guard.py` 增加启动期 schema guard，并在 FastAPI lifespan 中于 `create_all()` 后执行；当检测到旧 `sessions` 表缺少 `title` 列时，自动执行 `ALTER TABLE sessions ADD COLUMN IF NOT EXISTS title VARCHAR(255) NOT NULL DEFAULT 'Unnamed Chat';` 补齐结构。补充单元测试覆盖“表不存在 / 列已存在 / 缺列自动补齐”三种场景。验收标准保持不变：旧数据库不删库重启后可成功 `POST /api/sessions`，`GET /api/sessions` 返回 `title`，前端进入 `/chat/new` 不再触发 `column "title" does not exist`。
- 2026-05-06：工作台右侧栏宽度改为按整体比例存储与拖拽，而非固定像素宽度；`workspaceStore` 使用 `workspaceWidthRatio` 表示工作区占聊天页容器的比例，拖拽分隔条时根据当前容器宽度实时换算。为避免右栏挤压主对话区，当前允许范围设为 `22%` 到 `50%`，从而支持用户将右侧工作区拉大到页面一半，同时在窗口尺寸变化时保持相对布局稳定。
- 2026-05-06：中栏会话头部标题与左侧 Sidebar 历史对话名称对齐，统一使用会话详情/会话列表返回的 `sessions.title` 展示，不再直接显示 `sessionId`。`ChatWorkspace` 负责维护当前会话标题：初次进入会话时从 `getSession` 返回值设置，后续当 `listSessions` 刷新到异步生成的新标题后，同步更新中栏标题，避免左中两处名称不一致。
- 2026-05-06：聊天页三栏视觉收敛为更接近 OpenAI 的简洁白底工作区：左栏、中栏、右栏统一去除明显灰色渐变底和强卡片阴影，改为纯白背景 + 极轻分隔线 + 轻 hover 态；用户消息保留纯黑实底，助手消息与工作区卡片仅保留细边框。目标是降低三栏之间的割裂感，让布局更平、更轻，避免“每栏一块灰底”的拼贴效果。
- 2026-05-06：进一步修正聊天页 Sidebar 分隔线未拉满的问题：仅给 `ChatWorkspace` 设置 `min-h-screen` 还不够，因为 `AppSidebar` 原先使用 `h-full`，而父容器只有 `min-height` 没有显式 `height` 时，`height: 100%` 不会按整屏解析，Sidebar 仍可能只长到内容高度。现改为由 flex 布局直接拉伸 Sidebar（`self-stretch`），并在 `ChatWorkspace` 显式声明 `items-stretch`，保证左栏边线随三栏容器完整贯穿到底部。
- 2026-05-06：统一聊天页三栏顶部 header 高度，避免 Sidebar 标题区底线与中栏/右栏 header 底线错位。当前为 Sidebar、ChatPanel、WorkspacePanel 顶部统一设定 `72px` 高度，由显式高度控制对齐，而不是继续依赖各自不同的 padding 和内容自然撑开。
- 2026-05-06：Dashboard 左上角返回按钮改为回到聊天工作台而不是 root 首页。当前产品主入口已经是 `/chat/[sessionId]` 三栏工作台，Dashboard 属于工作台内配置页，因此返回目标统一为 `/chat/new`，避免用户从配置页误跳回非主工作流页面。
- 2026-05-06：补充会话自动命名能力：`sessions` 新增 `title` 字段，默认值为 `Unnamed Chat`；左侧历史对话不再显示 `sessionId`，改为显示 `title`。首轮对话完成后，后端在 assistant 首条消息落库后异步调用一次 LLM，根据“首条用户消息 + 首条助手回复”生成简短标题，并仅在当前标题仍是默认值时更新，失败则保留 `Unnamed Chat`。该命名流程不阻塞主 SSE 回复链路，避免影响首轮交互时延。
- 2026-05-06：会话管理修正二次落地：确认 `/chat/new` 卡住和重复建会话的根因不是单纯 effect 重跑，而是开发模式下组件可能卸载再重挂，`useRef` 无法跨挂载共享中的建会话请求；改为 `ChatSessionShell` 模块级 `pendingSessionCreation` promise 兜底。与此同时移除 sidebar 历史对话的前端 `slice(0, 8)` 上限，后端 `list_sessions` 改为默认不裁剪，避免随着会话数增加出现“新建后看不到/误判为失败”的体验问题。删除当前会话后改为先重新拉取最新会话列表，再决定跳转目标，避免使用过期列表导致跳转和删除状态不一致。
- 2026-05-06：E-2 前先修会话管理基础问题：`/chat/new` 的客户端建会话逻辑增加一次性保护，避免 Next.js 开发模式下 effect 重跑导致重复创建 session；左侧 Sidebar 增加显式“新建对话”入口；后端新增 `DELETE /api/sessions/{id}`，级联删除 `messages`、`reference_images`、`generation_tasks`；前端历史会话列表增加删除按钮，删除当前会话后自动跳转到下一条会话或 `/chat/new`。该修复属于前端主链路基础能力，优先于 E-2 继续扩展。
- 2026-05-06：E-1 后补充工作台布局交互：中栏与右栏之间增加桌面端拖拽分隔条，用户可直接用鼠标调整右侧工作区宽度；`workspaceStore` 新增 `workspaceWidth` / `workspaceCollapsed`，右栏支持像左侧 Sidebar 一样折叠，并保留窄恢复栏。该能力属于工作台壳层交互，先于 E-2 落地，避免后续在提示词/参考图工作区完成后再返工布局。
- 2026-05-06：E-1 完成：前端新增 `components/chat/*`、`hooks/useSSE.ts`、`store/chatStore.ts`、`store/workspaceStore.ts`，落地左中右三栏骨架、纯文字多轮对话、SSE 文本/工具/生成事件消费，以及右侧 Prompt/生成图占位标签；`/chat/new` 改为客户端创建真实会话后跳转。为保证刷新和历史可用，后端 `session.py` 新增 `GET /api/sessions` 会话列表与 `GET /api/sessions/{id}` 消息历史返回，前端在进入会话时加载历史消息并渲染左侧历史列表。E-1 仍不包含参考图上传、prompt/参数持久化和批注下载，这些保留到 E-2 以后。
- 2026-05-06：C-8 完成：`dashboard_service.py` 补齐 `embedding` 默认配置与 provider 列表，image provider 从残留 `openrouter` 改为 `grsai`，并增加 `__main__` 自检入口；`dashboard.py` 接受 `embedding` patch；`dashboard.yaml.example` 补齐 `embedding` 配置块并统一 `grsai` 命名；前端 `types.ts` 增加 `image_provider.model` 与 `embedding` 类型，Dashboard 新增 Embedding tab，图像生成平台配置增加 model 选择；`agent_graph.mmd` 改为当前 `agent -> rag_gate -> enhance_prompt -> generate_image -> evaluate_image -> refine_prompt` 的确定性子流程；`tests/services/test_dashboard_service.py` 更新为 `grsai`/`embedding` 并通过；前端 `npm run lint` 通过。
- 2026-05-06：前端目标调整为图像生成三栏工作台：左侧 Sidebar（历史对话、知识库、首页跳转、Dashboard、折叠）、中间多轮对话与生成图缩略图、右侧 Workspace 标签页（提示词与参考图 / 生成图片）。参考图上传需支持用户标注参考意图（构图、色彩、建筑样式、材质、光线、环境、其他）；右侧展示并允许编辑 prompt、参数滑块和风格模板；生成图支持预览、下载、Canvas 批注，批注图首版作为新参考图进入下一轮。E 阶段拆分为 E-1 三栏骨架、E-2 参考图工作区、E-3 参数/风格/prompt 同步、E-4 生成图批注下载、E-5 全流程联调。
- 2026-05-06：新增 `backend/scripts/test_chat_sse_flow.py` 独立联调脚本，连接真实 Docker Postgres/Redis，但使用 fake graph 避免真实 LLM/API 调用；覆盖消息去重、assistant 落库、Redis event buffer、`Last-Event-ID` 保守 replay、active run cancel 语义；在沙箱外运行 `.venv/bin/python scripts/test_chat_sse_flow.py` 通过。
- 2026-05-08：为恢复前端主对话链路，`agent_node` 改为优先调用 `_llm.astream`，将模型原始输出直接经 `QueueEmitter` 作为 `text_delta` 推送给前端；节点结束后仍对完整输出做 JSON 解析并更新 `design_state`、`phase`、`ready_to_generate`。当前 assistant 展示内容是模型原文，不再在 `agent_node` 内提取 `reply` 字段生成聊天消息；后续如需“流式展示原文，结束后替换为 reply 字段”，需在 SSE/前端消息状态上增加一次完成后替换逻辑。
- 2026-05-08：继续排查前端无流式显示问题后，确认高风险点在 Next.js 开发代理对 SSE 的转发链路。前端 `fetch` 与 `EventSource` 现统一支持通过 `NEXT_PUBLIC_API_BASE_URL` 直连后端，开发默认值设为 `http://localhost:8000`；`useSSE` 不再依赖相对路径 `/api/...`；后端 `main.py` 补充 `CORSMiddleware`，允许 `localhost/127.0.0.1:3000/3001` 跨域访问。此改动优先保证本地开发环境下 SSE 稳定直连，不再依赖 Next rewrite 对流式的兼容性。
- 2026-05-06：C-6.1 代码硬化完成：`POST /messages` 继续写 DB，Redis pending key 改为只存 `message_id` 作为 stream_id 首连握手，`GET /stream` 从 DB 最近 20 条构造 Graph 输入且不再追加 pending 内容；SSE 首次运行时收集 `text_delta` 并在 `done` 后写入 assistant 消息，断线重连不落库；新增 `active_run:{session_id}` 和 `cancel:{session_id}:{run_id}`，新消息会取消旧 run；`Last-Event-ID > 0` 采用保守重连语义，只 replay Redis event buffer，不重新运行 Agent；由于当前 `agent_node` 使用 `_llm.ainvoke`，`text_delta` 先用 `on_chain_stream` 中 AIMessage 的完整内容做兜底输出，不是真正逐 token 流式，后续如需打字机效果需单独重构。
- 2026-05-06：梳理当前架构与技术文档后，决定先不直接进入 D/E 大功能开发；新增 C-6.1 用于修稳后端 Chat/SSE 主链路（消息去重、AI 回复落库、`text_delta` 来源、新消息中断旧 run、断线重连验证），新增 C-8 用于修正 Dashboard provider/model/embedding 配置、`agent_graph.mmd` 和 `DEV_SPEC.md` 的实现漂移；推荐顺序调整为 C-6.1 → C-8 → E-1 → D → E-2/E-5 → C-7。
- 2026-05-05：C-6 完成（@observe 留 C-7）：`streaming.py` 用 ContextVar 注入 QueueEmitter，同时消费 `astream_events` 和 emitter queue，映射 7 种 SSE 事件；`chat.py` 两端点（POST 提交消息存 Redis pending key，GET 消费 SSE），stream_id == run_id，Redis 缓冲 TTL 60s 支持 Last-Event-ID 断线重连；`generate_image_node` 从 ContextVar 读取 emitter；chat router 注册到 main.py。
- 2026-05-05：C-5 完成：评分加权由后端代码计算（LLM 只输出各维度原始分），权重常量写在 `image_evaluator.py` 内；参考图相似度当前为整体综合评分，E 阶段扩展为按用户标注意图（构图/色彩/样式/材质）分维度评估，计划已写入文档；9 个单元测试全部通过。
- 2026-05-05：C-4 完成：prompt_builder（EnhancedPrompt Pydantic 校验，失败重试 1 次后 fallback）；Celery 方案 A（asyncio.run 包装，迁移方案 B 只改 task 装饰器）；image_generator 引入 SSEEmitter 协议 + NullEmitter 占位，C-6 注入真实 emitter，测试可用 MockEmitter；AgentState 新增 `_enhanced_prompt` / `_current_gen_result` 内部传递字段。
- 2026-05-05：C-3 完成：`StyleKeywords` 新增 `description` 字段（2-3 句风格说明，供 `enhance_prompt` LLM 参考），与 `mood`（一句话氛围，供 agent 对话）和 `positive`/`negative`（直接拼入图像生成 prompt）分工明确；`agent_node` 工具调用改为规则驱动（有图片 URL → 分析，有风格 → 查关键词），不使用 LLM bind_tools；`rag_gate_node` 按规则调用 `search_similar_cases`。
- 2026-05-05：C-1/C-2 完成：会话与消息 API（session_service / message_service / session 路由）；Agent 状态层全部子结构（ReferenceImageAnalysis / GenerationResult / EvaluationResult / ImageRecord）从 @dataclass 改为 TypedDict，确保 LangGraph checkpointer JSON 序列化兼容；AgentState 继承 MessagesState（带 add_messages reducer 的 TypedDict）；checkpointer 生命周期改为 FastAPI lifespan async with 管理，graph 在 lifespan 内编译后存入 app.state.graph；安装 langgraph-checkpoint-postgres 3.0.5 + psycopg[binary,pool]。
- 2026-05-05：Agent 架构优化：从”纯 ReAct 自由调用完整生成链路”调整为”agent 决策节点 + rag_gate + 确定性生成子流程”；图像生成、评估、重试由 Graph 控制，`retry_count` 仅作用于当前生成任务；新增 `turn_id` / `run_id` / `phase` / `current_task_id` / `best_generation_result` / `last_search_signature` 等运行态字段；用户中断从内存 `cancel_event` 调整为 Redis cancel flag（`cancel:{session_id}:{run_id}`）；RAG 触发从完全自主决策改为规则门控；MCP 只向 Agent 暴露检索工具，`store_generated_image` 仅由 `POST /api/library/store` 直接调用。
- 2026-05-04：Embedding 提供商从百炼切换至火山引擎：文本 embedding 改用 doubao-embedding（2048 维，OpenAI 兼容 endpoint），图像 embedding 改用 doubao-embedding-vision-251215（3072 维，multimodal endpoint）；Milvus Collection 向量维度同步更新（caption_vector 1024→2048，image_vector 768→3072）；dashboard.yaml 新增 embedding 配置块；工厂 key 从 bailian 改为 volcengine。
- 2026-05-04：确认 Agent 流程设计：`store_generated_image` 解耦出 Agent，改为前端按钮触发独立 REST 接口 POST /api/library/store；生成流程最初设计为标准 ReAct，已于 2026-05-05 调整为确定性生成子流程。
- 2026-05-04：B-3 图像生成客户端：用 GrsAI（`grsai_client.py`）替换 OpenRouter，GrsAI 同步返回图片 URL（`results[0].url`），支持 `gpt-image` / `nano-banana` 模型，工厂 `create` 方法新增 `model` 参数。
- 2026-05-01：完成 B-2 文件存储模块：新增 `storage_service.py` 与 `POST /api/upload`，上传仅接收二进制文件（multipart/form-data），MIME 白名单 `jpeg/png/webp`；本地存储路径为 `backend/uploads`，返回 `/static/uploads/{filename}`；`STORAGE=minio` 分支暂抛 `NotImplementedError`，避免静默失败。
- 2026-05-01：完成 B-1 LLM 客户端：httpx.AsyncClient 统一调用，公共逻辑提取到 `_base_http_client.py`，两个平台客户端只声明 endpoint；内部重试 2 次；`astream` 手动解析 SSE；`LLMClient` 调度器按 images 是否为空路由到 `ainvoke` 或 `ainvoke_with_vision`；后续支持 prompt cache 时通过 `_extra_payload()` hook 在各子类 override，无需重构。
- 2026-05-01：完成 A-4 Dashboard 配置模块：后端新增 `dashboard_service.py` 与 `dashboard.py` 路由（`GET/PUT /api/dashboard/config`、`GET /api/dashboard/providers`）；`PUT /config` 改为严格字段校验（仅允许 llm/image_provider/langfuse 及其定义字段），并采用部分更新（merge patch）；前端 Dashboard 调整为左侧导航（Model Config / Langfuse）+ 独立参数块（LLM、Image Provider、Langfuse）+ 顶部返回主界面按钮。
- 2026-05-01：完成 A-3 前端初始化：创建 Next.js（App Router + TypeScript + Tailwind）项目，接入 shadcn/ui 与 zustand，落地 `/`、`/chat/[sessionId]`、`/dashboard` 基础路由；开发环境端口改为 3001，前端通过 `next.config.ts` rewrites 代理 `/api/*` 到 `http://localhost:8000/api/*`
- 2026-04-30：确定使用 LangGraph 搭建 Agent，替代原方案中的自定义 architect_agent.py
- 2026-04-30：记忆系统分为短期/工作/参考图/长期四个层次
- 2026-04-30：历史决策：图像生成使用 Celery 异步队列，前端轮询状态；已于 C-6/C-6.1 调整为 Agent SSE 主链路推送 `generation_start/done`，独立 REST 轮询接口保留为后续规划
- 2026-04-30：图像生成服务选用云端 API，支持三个平台：阿里云百炼（Qwen）、火山引擎豆包、GrsAI
- 2026-04-30：不做用户登录系统，改为 Dashboard 页面供用户配置模型和 API Key
- 2026-04-30：LangGraph checkpointer 使用 PostgreSQL（langgraph-checkpoint-postgres）
- 2026-04-30：Langfuse 使用 Docker 自部署，纳入 docker-compose.yml
- 2026-04-30：Dashboard API Key 明文存配置文件（`backend/config/dashboard.yaml`），内部工具无需加密
- 2026-04-30：新增 image-rag-mcp 独立服务，通过 stdio 与 Agent 通信
- 2026-04-30：向量存储策略：caption_vector（文字检索）+ image_vector（以图搜图）双向量存 Milvus，提示词和元数据存 PostgreSQL image_library 表，通过 image_id 关联
- 2026-04-30：VLM Caption 复用对话 LLM API（从 dashboard_config 读取配置），不单独部署模型
- 2026-04-30：历史决策：Agent 改为 ReAct 循环模式，原固定节点（check_completeness 等）改为工具调用；已于 2026-05-05 调整为 agent 决策节点 + 确定性生成子流程
- 2026-04-30：历史决策：工具集确定为 8 个，分信息收集/生成执行/生成后处理三组；`store_generated_image` 后续已移出 Agent，生成执行/评估/重试已改为 Graph 确定性子流程
- 2026-04-30：AgentState 新增 generation_results、retry_count、last_evaluation、similar_cases 字段；2026-05-05 补充运行态字段
- 2026-04-30：历史决策：ReAct 循环边界为重试上限 3 次、工具调用总步数 25（recursion_limit）、用户中断（interrupt_before）、评估兜底返回最高分结果；已于 2026-05-05 调整为确定性生成子流程边界，`recursion_limit` 仍保留在 Graph 调用配置中
- 2026-04-30：SSE 事件协议确定 7 种事件类型；工具状态半透明展示；generate_image 解耦推送；支持 Last-Event-ID 断线重连
- 2026-04-30：图像生成平台统一接口采用抽象工厂模式 + httpx；三平台格式差异封装在各客户端内，工具层只调用统一调度器
- 2026-04-30：对话模型改为 VLM，支持百炼（Qwen3-VL）和火山引擎豆包 VLM，Dashboard 可切换；LLM 层同样采用工厂模式，平台范围限定为百炼和火山引擎
- 2026-04-30：MCP 框架选用 FastMCP（mcp.server.fastmcp，官方 mcp 库内置）
- 2026-04-30：历史决策：Embedding 模型选用百炼 text-embedding-v3（已于 2026-05-04 被火山引擎 embedding 方案覆盖）；pg_client.py 负责 image_library 表 CRUD，通过 image_id 关联 Milvus 向量

---

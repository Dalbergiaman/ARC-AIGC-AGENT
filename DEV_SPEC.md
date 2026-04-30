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
| 图像生成 | 云端 API：阿里云百炼（万相）/ 火山引擎（即梦）/ OpenRouter |
| 数据库 | PostgreSQL + SQLAlchemy |
| LangGraph Checkpointer | PostgreSQL（langgraph-checkpoint-postgres） |
| 任务队列 | Celery + Redis |
| 文件存储 | 本地开发 / MinIO 生产 |
| 前端状态 | Zustand |
| 前端 UI | Tailwind CSS + shadcn/ui |
| 可观测性 | Langfuse（LLM 调用追踪、Prompt 版本管理） |
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
         ├── 图像生成（云端 API：百炼 / 豆包 / OpenRouter）
         └── 对象存储（本地 / MinIO / S3）
```

---

## 项目目录结构

```
aigc_agent/
├── DEV_SPEC.md                         # 本文件
├── docker-compose.yml
├── image-rag-mcp/                      # 独立 MCP 服务（stdio 通信）
│   ├── server.py                       # FastMCP stdio 入口（from mcp.server.fastmcp import FastMCP）
│   ├── tools/
│   │   ├── store.py                    # store_generated_image 工具
│   │   ├── search.py                   # search_by_text / search_by_image 工具
│   │   └── retrieve.py                 # get_image_by_id 工具
│   ├── core/
│   │   ├── embedding/                  # Embedding 模块（独立文件夹）
│   │   │   ├── base.py                 # 抽象基类 EmbeddingClientBase
│   │   │   └── bailian.py              # 百炼 text-embedding-v3 客户端（云端调用）
│   │   ├── vlm_caption.py              # 调用对话 LLM API 生成图片 Caption
│   │   ├── clip_encoder.py             # 图片 → CLIP 向量（以图搜图用）
│   │   ├── milvus_client.py            # Milvus 操作封装
│   │   └── pg_client.py               # PostgreSQL 操作封装（image_library 表 CRUD，image_id 关联 Milvus）
│   └── requirements.txt
├── frontend/                           # Next.js 前端
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   ├── chat/[sessionId]/page.tsx
│   │   └── dashboard/page.tsx          # Dashboard：模型配置、API Key 管理
│   ├── components/
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── InputBar.tsx
│   │   │   └── ImageUploader.tsx
│   │   ├── gallery/
│   │   │   └── ResultGallery.tsx
│   │   └── dashboard/
│   │       ├── ModelSelector.tsx       # 对话模型选择（百炼/火山引擎 VLM）
│   │       ├── ImageProviderConfig.tsx # 图像生成平台配置（百炼万相/火山即梦/OpenRouter）
│   │       └── ApiKeyForm.tsx          # API Key 填写与保存
│   ├── hooks/
│   │   ├── useChat.ts
│   │   ├── useSSE.ts
│   │   └── useImageGeneration.ts
│   ├── store/
│   │   └── chatStore.ts
│   └── lib/
│       ├── api.ts
│       └── types.ts
└── backend/                            # FastAPI 后端
    ├── main.py
    ├── config.py
    ├── requirements.txt
    ├── api/
    │   └── routes/
    │       ├── chat.py
    │       ├── generation.py
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
    │       ├── style_lookup.py         # lookup_style_keywords — 查询风格关键词库
    │       ├── prompt_builder.py       # enhance_prompt + refine_prompt — Prompt 构建与修正
    │       ├── image_generator.py      # generate_image — 调用 core/image/generator
    │       ├── image_evaluator.py      # evaluate_generated_image — 视觉 LLM 评估生成结果
    │       ├── store_to_library.py     # store_to_library — 调用 image-rag-mcp 存图
    │       ├── search_library.py       # search_similar_cases — 调用 image-rag-mcp 检索
    │       └── prompt_templates.py     # 纯数据文件：风格关键词库，被 style_lookup/prompt_builder 引用
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
    │       └── openrouter_client.py    # OpenRouter 客户端
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

```python
class AgentState(TypedDict):
    messages: list[BaseMessage]          # 对话历史
    design_state: DesignState            # 结构化设计参数（工作记忆核心）
    reference_images: list[ReferenceImageAnalysis]  # 参考图分析结果
    ready_to_generate: bool              # 控制流：是否触发生成
    generation_results: list[GenerationResult]      # 历史生成结果
    retry_count: int                     # 当前重试次数（上限 3）
    last_evaluation: EvaluationResult | None        # 最近一次评估结果
    similar_cases: list[ImageRecord]     # RAG 检索到的参考案例
```

### DesignState 结构

```python
class DesignState(TypedDict):
    building_type: str        # 建筑类型（别墅/商业/办公...）
    style: str                # 风格（极简/新中式/工业风...）
    facade_material: str      # 外立面材质
    lighting: str             # 光线（时段/方向/氛围）
    viewpoint: str            # 视角（人视/鸟瞰/仰视...）
    season: str               # 季节/天气
    surroundings: str         # 周边环境
    color_palette: str        # 色彩倾向
    special_requirements: str # 特殊需求
    completeness: float       # 信息完整度 0.0~1.0
```

### Graph 节点与流转（ReAct 循环）

```
用户消息进入
    │
    ▼
[agent 节点] — LLM 思考，决定调用哪个工具
    │
    ├── analyze_reference_image()   有参考图且未分析时
    ├── lookup_style_keywords()     需要风格关键词参考时
    ├── search_similar_cases()      需要历史案例参考时
    ├── enhance_prompt()            设计信息充分，准备生成时
    │       │
    │       ▼
    │   generate_image()
    │       │
    │       ▼
    │   evaluate_generated_image()
    │       │
    │       ├── score < 0.8 且 retry_count < 3
    │       │       │
    │       │       └── refine_prompt() → generate_image() → evaluate...（循环）
    │       │
    │       └── score >= 0.8 或 retry_count == 3
    │               │
    │               ├── retry_count == 3：取 generation_results 中 score 最高的结果
    │               └── 回复用户展示结果，询问是否存入图库
    │                       │
    │                   用户确认 → store_to_library()
    │
    ├── 直接回复用户（信息不足时追问）
    │
    └── [用户中断] 任意时刻发新消息
            │
            └── interrupt_before 暂停当前循环 → 注入新消息 → Agent 重新决策
```

**工具说明**

| 工具 | 输入 | 输出 | 调用时机 |
|------|------|------|----------|
| `analyze_reference_image` | image_url | ReferenceImageAnalysis | 用户上传参考图后 |
| `lookup_style_keywords` | style: str | StyleKeywords | 需要风格关键词时 |
| `search_similar_cases` | query, filters | list[ImageRecord] | collect_info 阶段，RAG 参考 |
| `enhance_prompt` | design_state, reference_analysis | EnhancedPrompt | 信息充分，首次生成前 |
| `generate_image` | prompt, negative_prompt, ref_image_url, params | GenerationResult | 每次触发生成 |
| `evaluate_generated_image` | image_url, design_state, reference_images | EvaluationResult | 每次生成后自动评估 |
| `refine_prompt` | original_prompt, evaluation | EnhancedPrompt | 评估不满意时修正 |
| `store_to_library` | image_url, prompt, design_state, session_id | image_id | 用户确认存入图库时 |

### ReAct 循环边界控制

| 边界 | 机制 | 参数 | 兜底行为 |
|------|------|------|----------|
| 生成重试上限 | `retry_count` 字段计数 | 最多 3 次 | 返回 `generation_results` 中 score 最高的结果 |
| 工具调用总步数 | LangGraph `recursion_limit` | 25 步 | 超出后抛出异常，捕获后返回当前最优结果 |
| 用户中断 | LangGraph `interrupt_before=["agent"]` | 每轮 agent 节点前可中断 | 收到新消息时终止当前循环，进入新一轮 |
| 评估分数兜底 | `retry_count == 3` 时从 `generation_results` 取最优 | `max(results, key=lambda r: r.score)` | 告知用户"已达最大重试次数，返回最佳结果" |

**用户中断实现说明**：LangGraph 的 `interrupt_before` 在每次进入 `agent` 节点前暂停，FastAPI 侧收到新的用户消息时恢复执行（`graph.update_state` 注入新消息），Agent 自动感知上下文变化决定是否放弃当前生成任务。

---

## SSE 流式输出设计

### 事件协议

每个 SSE 事件格式：`event: <type>\ndata: <JSON>\nid: <递增ID>\n\n`

| 事件类型 | 触发时机 | data 结构 |
|----------|----------|-----------|
| `text_delta` | LLM 逐字输出 | `{"content": "..."}` |
| `tool_start` | Agent 开始调用工具 | `{"tool": "analyze_reference_image", "input": {...}}` |
| `tool_end` | 工具调用完成 | `{"tool": "...", "summary": "用户友好的一句话摘要"}` |
| `generation_start` | 图像生成任务提交 | `{"task_id": "xxx", "provider": "bailian"}` |
| `generation_done` | 图像生成完成 | `{"task_id": "xxx", "image_url": "...", "score": 0.85, "retry_count": 1}` |
| `error` | 发生错误 | `{"code": "GENERATION_TIMEOUT", "message": "..."}` |
| `done` | 本轮响应结束 | `{"finish_reason": "stop \| max_retries \| interrupted"}` |

`finish_reason` 三种值：
- `stop`：正常结束
- `max_retries`：达到重试上限，已返回最高分结果
- `interrupted`：用户中断当前循环

### 后端实现（`core/llm/streaming.py`）

从 LangGraph `astream_events` 过滤并映射到上述协议：

- `on_chat_model_stream` → `text_delta`
- `on_tool_start` → `tool_start`
- `on_tool_end` → `tool_end`（原始输出经 `summarize_tool_output` 转为用户友好摘要）
- `generate_image` 工具内部完成后额外推送 `generation_start` / `generation_done`

### 前端消费（`hooks/useSSE.ts`）

按 `event` 字段分发：

- `text_delta`：追加到当前 AI 消息气泡
- `tool_start` / `tool_end`：消息气泡下方显示小状态条（"正在分析参考图..."），完成后自动收起
- `generation_start`：显示生成中占位卡片（loading 动画）
- `generation_done`：替换占位卡片为真实图片
- `error`：展示错误提示
- `done`：结束当前消息，根据 `finish_reason` 决定 UI 状态

### 关键细节

**工具状态半透明展示**：`tool_start/end` 显示为消息下方的小状态条，不打断主对话流，完成后自动收起，用户可感知 Agent 行为但不被技术细节干扰。

**`generate_image` 的解耦处理**：该工具内部是 Celery 异步任务，对 Agent 暴露为同步接口（内部轮询）。`tool_start` 时立即推送 `generation_start`，Celery 完成后推 `generation_done`，避免前端长时间无响应。

**断线重连**：每个事件携带递增 `id`，前端 `EventSource` 断开重连时传 `Last-Event-ID`，后端从断点续传。

---

## 图像生成平台统一接口设计

### 选型结论：httpx 统一 POST

三个平台 API 格式差异大，openai 库只能覆盖 OpenRouter，无法统一。使用 httpx 异步客户端统一调用，配合抽象工厂模式封装差异。

| 平台 | Endpoint | 格式 | OpenAI 兼容 |
|------|----------|------|------------|
| 阿里云百炼（万相） | `POST /api/v1/services/aigc/text2image/image-synthesis` | 异步任务制（提交→轮询） | 否，DashScope 私有格式 |
| 火山引擎豆包 | `POST /api/v3/images/generations` | 类 OpenAI images 格式 | 部分兼容 |
| OpenRouter | `POST /api/v1/chat/completions` | Chat Completions + `modalities: ["image"]` | 是，但走 chat 接口 |

### 抽象工厂结构

```
core/image/
├── base.py          # 抽象基类 ImageGeneratorBase + 统一数据结构
├── factory.py       # ImageGeneratorFactory，按 provider 名称实例化
├── generator.py     # 调度器，从 dashboard_config 读取当前平台后调用工厂
├── bailian_client.py
├── volcengine_client.py
└── openrouter_client.py
```

**统一数据结构**

```python
@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str
    ref_image_url: str | None
    width: int = 1344
    height: int = 768
    steps: int = 30
    seed: int | None = None

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
        "openrouter": OpenRouterClient,
    }

    @classmethod
    def create(cls, provider: str, api_key: str) -> ImageGeneratorBase:
        return cls._registry[provider](api_key)
```

### 三个客户端的核心差异

**百炼（`bailian_client.py`）**
异步任务制，两步：提交任务拿 `task_id` → 轮询 `/api/v1/tasks/{task_id}` 直到 `SUCCEEDED`。轮询逻辑封装在客户端内部，对外暴露同步接口。

**豆包（`volcengine_client.py`）**
同步返回，直接 POST 拿结果，响应结构类似 OpenAI images API，从 `data[0].url` 取图片 URL。

**OpenRouter（`openrouter_client.py`）**
走 chat completions 接口，`modalities: ["image"]`，响应从 `choices[0].message.images[0]` 取 base64 图片数据，需上传到存储服务后返回 URL。

### 调度器

```python
# generator.py
class ImageGenerator:
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        config = await dashboard_service.get_config("image_provider")
        client = ImageGeneratorFactory.create(
            provider=config["provider"],
            api_key=config["api_key"]
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

### 抽象基类

```python
class EmbeddingClientBase(ABC):
    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量文本转向量，百炼支持批量调用，效率更高"""
        ...

    async def embed(self, text: str) -> list[float]:
        """单条便捷方法，内部调用 embed_batch"""
        return (await self.embed_batch([text]))[0]
```

### 百炼实现（`bailian.py`）

- 模型：`text-embedding-v3`
- 向量维度：1536
- 调用方式：httpx POST，云端 API

### 工厂

```python
class EmbeddingFactory:
    _registry = {
        "bailian": BailianEmbedding,
    }

    @classmethod
    def create(cls, provider: str, api_key: str) -> EmbeddingClientBase:
        return cls._registry[provider](api_key)
```

当前只有百炼一个实现，工厂模式保持与 LLM / 图像生成模块的一致性，后续扩展无需改调用方。

---

## 图像评估评分设计

### EvaluationResult 数据结构

```python
@dataclass
class EvaluationResult:
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
| 长期记忆 | 用户风格偏好、历史反馈 | user_preferences 表 | 跨会话 |

---

## Langfuse 集成设计

### 追踪方式：`@observe` 显式装饰

每个节点函数和工具函数都加 `@observe()`，追踪粒度到函数级别。LLM 调用内部细节通过 `langfuse_context` 手动关联。

**入口 Trace**：每轮用户消息在 `chat.py` 路由处包一个最外层 Trace，内部所有被装饰的节点和工具自动成为子 Span。

```python
from langfuse.decorators import observe, langfuse_context

@observe(name="agent:turn")   # 最外层 Trace
async def handle_message(session_id: str, message: str):
    langfuse_context.update_current_trace(
        session_id=session_id,
        user_id="anonymous"
    )
    await graph.ainvoke(...)
```

**Agent 节点**（ReAct 只有一个 agent 节点）：

```python
@observe(name="node:agent")
async def agent_node(state: AgentState) -> AgentState:
    langfuse_context.update_current_observation(
        input=state["messages"][-1].content,
        metadata={"design_state": state["design_state"], "retry_count": state["retry_count"]}
    )
    result = await llm.ainvoke(...)
    langfuse_context.update_current_observation(output=result.content)
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
  ├── Span: node:agent（第 1 轮思考）
  ├── Span: tool:analyze_reference_image
  ├── Span: node:agent（第 2 轮思考）
  ├── Span: tool:lookup_style_keywords
  ├── Span: node:agent（第 N 轮思考）
  ├── Span: tool:enhance_prompt
  ├── Span: tool:generate_image
  ├── Span: tool:evaluate_generated_image
  └── Span: tool:refine_prompt（重试时出现，后接新一轮 node:agent）
```

### Prompt 本地管理：`agent/prompts.py`

Prompt 不存 Langfuse，统一放在 `agent/prompts.py`，用函数封装（方便传入变量），版本管理走 git。

| 函数名 | 用途 | 变量参数 |
|--------|------|----------|
| `collect_info_system()` | collect_info 节点 System Prompt | `design_state`, `style_keywords`, `reference_analysis` |
| `enhance_prompt_system()` | enhance_prompt 工具指令 | `design_state`, `reference_analysis`, `similar_cases` |
| `evaluate_image_system()` | evaluate_generated_image 工具指令 | `design_state` |
| `refine_prompt_system()` | refine_prompt 工具指令 | `original_prompt`, `evaluation_result` |
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
        "args": ["image-rag-mcp/server.py"],
        "transport": "stdio"
    }
})
mcp_tools = await mcp_client.get_tools()  # 自动转为 LangChain Tool
# 与本地工具合并后传给 Agent
all_tools = local_tools + mcp_tools
```

MCP 进程由 `MultiServerMCPClient` 管理生命周期，FastAPI 启动时初始化，关闭时自动终止。

---

## 图像生成任务流转（Celery）

### 状态存储

Celery result backend 使用 Redis，`task_id` 存入 `AgentState`，工具内部轮询 Redis 直到任务完成。

### `generate_image` 工具内部流程

```python
# 1. 提交 Celery 任务，立即推送 generation_start 事件
task = generate_image_task.delay(request)
yield SSEEvent("generation_start", {"task_id": task.id, "provider": provider})

# 2. 轮询 Redis，每 2s 检查一次，最多等 120s
for _ in range(60):
    result = AsyncResult(task.id)
    if result.ready():
        gen_result = result.get()
        yield SSEEvent("generation_done", {...})
        return gen_result
    await asyncio.sleep(2)

# 3. 超时处理：计入重试次数，推送 error 事件
state["retry_count"] += 1
yield SSEEvent("error", {"code": "GENERATION_TIMEOUT", "message": "生成超时，正在重试..."})
raise TimeoutError("generation timeout")
```

超时后 Agent 自行决策是否重试（受 `retry_count <= 3` 约束）。

---

## 参考图上传流程

### 存储策略

通过 `storage_service` 抽象屏蔽环境差异：

| 环境 | 存储位置 | URL 格式 |
|------|----------|----------|
| 本地开发 | `backend/uploads/` 目录 | `http://localhost:8000/static/uploads/{uuid}.jpg` |
| 生产 | MinIO | `http://minio:9000/bucket/{uuid}.jpg` |

切换通过环境变量 `STORAGE=local|minio` 控制。

### 上传接口响应

```json
// POST /api/upload 响应
{
  "file_id": "uuid",
  "url": "http://localhost:8000/static/uploads/xxx.jpg"
}
```

前端拿到 `url` 用于预览，同时将 `url` 附在下一条消息里发给 Agent。Agent 收到后将 `url` 存入 `AgentState.reference_images`，并调用 `analyze_reference_image(image_url=url)` 进行视觉分析。

---

## API 接口

```
POST   /api/sessions                              创建会话
GET    /api/sessions/{session_id}                 获取会话详情
POST   /api/chat/sessions/{session_id}/messages   发送消息（SSE 流）
POST   /api/upload                                上传参考图
POST   /api/generation/tasks                      触发图像生成
GET    /api/generation/tasks/{task_id}/status     查询生成状态
GET    /api/generation/sessions/{id}/results      获取生成结果列表
GET    /api/dashboard/config                      获取当前配置
PUT    /api/dashboard/config                      保存配置（模型、API Key 等）
GET    /api/dashboard/providers                   获取支持的图像生成平台列表
```

---

## 数据库表结构

```sql
-- 主业务库（PostgreSQL）
sessions          (id, design_state JSON, created_at)
messages          (id, session_id, role, content, created_at)
reference_images  (id, session_id, file_id, url, analysis JSON)
generation_tasks  (id, session_id, prompt, image_url, status, created_at)
-- LangGraph checkpointer 表由 langgraph-checkpoint-postgres 自动创建
-- Dashboard 配置不存 DB，改用 backend/config/dashboard.yaml（见下方说明）

-- 图库库（PostgreSQL，image-rag-mcp 使用）
image_library (
    id              UUID PRIMARY KEY,   -- 与 Milvus 向量的关联键
    session_id      UUID,
    image_url       TEXT,
    caption         TEXT,               -- VLM 生成的图片描述
    prompt          TEXT,               -- 正向提示词
    negative_prompt TEXT,
    design_state    JSON,               -- 完整设计参数
    provider        TEXT,               -- 生成平台
    created_at      TIMESTAMP
)
```

**Milvus Collection（向量库）**
```
image_id        # 主键，对应 image_library.id
caption_vector  # VLM caption → embedding（文字检索用）
image_vector    # CLIP 图片向量（以图搜图用）
style           # 标量过滤字段
building_type   # 标量过滤字段
image_url       # 标量字段，直接返回预览
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
  provider: bailian        # bailian | volcengine | openrouter
  api_key: sk-xxx

langfuse:
  host: http://localhost:3000
  public_key: pk-xxx
  secret_key: sk-xxx
```

`backend/config/dashboard.yaml.example` 作为模板提交到 git，实际配置文件加入 `.gitignore`。

---

## Docker Compose 服务组成

开发环境四个基础服务，文件存储用本地目录（不含 MinIO）：

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

  milvus:
    image: milvusdb/milvus:v2.4.0
    ports: ["19530:19530", "9091:9091"]

  langfuse:
    image: langfuse/langfuse:latest
    ports: ["3000:3000"]
    depends_on: [postgres]
    environment:
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/langfuse
```

启动顺序：postgres → redis + milvus（并行）→ langfuse。生产环境 MinIO 单独部署，切换 `STORAGE=minio` 环境变量即可。

---

## search_similar_cases 触发与使用

**触发时机**：Agent 自主决策，不设硬性规则。`prompts.py` 中给出调用建议：用户描述了建筑风格或类型后，建议调用一次 `search_similar_cases`，将结果存入 `AgentState.similar_cases`。

**结果使用**：`similar_cases` 作为参数传给 `enhance_prompt`，LLM 参考历史案例的提示词风格来生成新提示词。

```python
async def enhance_prompt(
    design_state: DesignState,
    reference_analysis: list[ReferenceImageAnalysis],
    similar_cases: list[ImageRecord]   # RAG 检索结果，可为空列表
) -> EnhancedPrompt:
    ...
```

`similar_cases` 为空时 `enhance_prompt` 正常工作，RAG 只是锦上添花，不是必要依赖。

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

---

## 开发进度

---

### A 阶段：基础设施与项目骨架

> 目标：本地开发环境全部跑通，后端和前端项目可以启动，数据库连接正常。

**A-1 基础设施启动**

- [x] 编写 `docker-compose.yml`（postgres:16 / redis:7-alpine / etcd:v3.5.18 / minio / milvus:v2.4.17 / langfuse:2 / attu:v2.4）
- [x] 配置 Langfuse 环境变量（`DATABASE_URL` 指向 postgres，共用实例不同 database）
- [x] 验证七个服务全部健康启动（`docker compose up -d`）
- [x] 创建 `backend/config/dashboard.yaml.example` 模板文件

> ⚠️ 注意：Milvus 依赖 etcd 和 minio 作为内部组件，官方 standalone 镜像已内置，直接用 `milvusdb/milvus:v2.4.0` 即可，不需要额外配置。

**A-2 后端项目初始化**

- [x] 创建 `backend/` 目录，初始化 Python 虚拟环境（uv），安装依赖（fastapi / uvicorn / sqlalchemy / asyncpg / langgraph / langchain-mcp-adapters / celery / redis / httpx / pyyaml / langfuse）
- [x] 编写 `backend/main.py`（FastAPI 应用入口，挂载路由，lifespan 自动建表）
- [x] 编写 `backend/config.py`（从环境变量读取 DB_URL / REDIS_URL 等，pydantic-settings）
- [x] 编写 `backend/models/database.py`（SQLAlchemy async engine + session）
- [x] 编写 `backend/models/schemas.py`（sessions / messages / reference_images / generation_tasks 表定义）
- [x] 启动验证：`/health` 返回 200，四张表自动创建成功

> ⚠️ 注意：SQLAlchemy 使用异步模式（`asyncpg` driver），engine 用 `create_async_engine`，session 用 `AsyncSession`。

**A-3 前端项目初始化**

- [ ] 在 `frontend/` 下初始化 Next.js 项目（App Router / TypeScript / Tailwind CSS）
- [ ] 安装依赖（shadcn/ui / zustand）
- [ ] 创建基础路由：`/`（首页）、`/chat/[sessionId]`、`/dashboard`
- [ ] 验证 `npm run dev` 正常启动

**A-4 Dashboard 配置模块**

- [ ] 编写 `backend/services/dashboard_service.py`（读写 `backend/config/dashboard.yaml`，缺失 key 返回默认值）
- [ ] 编写 `backend/api/routes/dashboard.py`（`GET /api/dashboard/config` / `PUT /api/dashboard/config` / `GET /api/dashboard/providers`）
- [ ] 编写前端 `dashboard/page.tsx` + `ModelSelector` / `ImageProviderConfig` / `ApiKeyForm` 组件，调用 Dashboard API 保存配置

> 🧪 测试：`tests/services/test_dashboard_service.py`
> - YAML 正常读写
> - 缺失 key 时返回默认值，不抛异常
> - 写入后再读取值一致

---

### B 阶段：核心能力层

> 目标：LLM 客户端、图像生成客户端、Embedding 客户端全部可独立调用，不依赖 Agent。

**B-1 LLM 客户端**

- [ ] 编写 `core/llm/base.py`（`LLMClientBase` 抽象基类，定义 `ainvoke` / `ainvoke_with_vision` / `astream` 三个方法）
- [ ] 编写 `core/llm/bailian_client.py`（httpx 调用百炼 `/compatible-mode/v1/chat/completions`，图片放 `content[].image_url`）
- [ ] 编写 `core/llm/volcengine_client.py`（httpx 调用豆包 `/api/v3/chat/completions`，格式同上）
- [ ] 编写 `core/llm/factory.py`（`LLMClientFactory`，注册 bailian / volcengine）
- [ ] 编写 `core/llm/client.py`（`LLMClient` 调度器，从 `dashboard_service` 读取配置，有图片时路由到 `ainvoke_with_vision`）

> ⚠️ 注意：两个平台的 `model` 字段名称不同，百炼用 `qwen-vl-max`，豆包用具体的 endpoint model id，需从 dashboard.yaml 的 `model` 字段读取，不要硬编码。

> 🧪 测试：`tests/core/llm/test_factory.py`
> - 注册的 provider 能正确实例化
> - 未知 provider 抛 `KeyError` 或自定义异常
>
> `tests/core/llm/test_client.py`
> - `images=None` 时调用 `ainvoke`
> - `images` 非空时调用 `ainvoke_with_vision`

**B-2 图像生成客户端**

- [ ] 编写 `core/image/base.py`（`ImageGeneratorBase` 抽象基类 + `GenerationRequest` / `GenerationResult` dataclass）
- [ ] 编写 `core/image/factory.py`（`ImageGeneratorFactory`，注册 bailian / volcengine / openrouter）
- [ ] 编写 `core/image/bailian_client.py`（httpx，提交任务拿 `task_id` → 轮询 `/api/v1/tasks/{task_id}` 直到 `SUCCEEDED`，轮询间隔 3s，超时 120s）
- [ ] 编写 `core/image/volcengine_client.py`（httpx，同步返回，从 `data[0].url` 取图片 URL）
- [ ] 编写 `core/image/openrouter_client.py`（httpx，从 `choices[0].message.images[0]` 取 base64，上传到 `storage_service` 后返回 URL）
- [ ] 编写 `core/image/generator.py`（`ImageGenerator` 调度器，从 dashboard.yaml 读取平台配置）
- [ ] 配置 Celery（`backend/celery_app.py`，broker=Redis，result_backend=Redis）
- [ ] 编写 Celery task `generate_image_task`，内部调用 `ImageGenerator.generate()`

> ⚠️ 注意：百炼图像生成是异步任务制，轮询逻辑封装在客户端内部，对外暴露同步接口。OpenRouter 返回 base64，需先上传到本地存储再返回 URL，不能直接把 base64 传给前端。

> 🧪 测试：`tests/core/image/test_factory.py`
> - 注册的 provider 能正确实例化
> - 未知 provider 抛异常

**B-3 文件存储模块**

- [ ] 编写 `backend/services/storage_service.py`（`STORAGE=local` 时写 `backend/uploads/`，返回 `/static/uploads/{uuid}.ext`；`STORAGE=minio` 时上传 MinIO）
- [ ] 在 `main.py` 挂载 `/static` 静态文件目录（开发环境）
- [ ] 编写 `backend/api/routes/upload.py`（`POST /api/upload`，返回 `{file_id, url}`）

> ⚠️ 注意：上传文件需校验 MIME 类型，只允许 `image/jpeg` / `image/png` / `image/webp`，防止上传非图片文件。

**B-4 Embedding 客户端（image-rag-mcp）**

- [ ] 编写 `image-rag-mcp/core/embedding/base.py`（`EmbeddingClientBase`，定义 `embed_batch` 抽象方法，`embed` 单条便捷方法）
- [ ] 编写 `image-rag-mcp/core/embedding/bailian.py`（httpx 调用百炼 text-embedding-v3，向量维度 1536）
- [ ] 编写 `image-rag-mcp/core/embedding/factory.py`（`EmbeddingFactory`，注册 bailian）

---

### C 阶段：Agent 核心

> 目标：Agent 可以完整跑通一轮对话 → 生成图片 → 评估 → 重试的完整流程。

**C-1 会话与消息 API**

- [ ] 编写 `backend/services/session_service.py` / `message_service.py`（sessions / messages 表 CRUD）
- [ ] 编写 `backend/api/routes/session.py`（`POST /api/sessions` / `GET /api/sessions/{id}`）

**C-2 Agent 状态与 Graph 骨架**

- [ ] 编写 `backend/agent/state.py`（`AgentState` / `DesignState` / `ReferenceImageAnalysis` / `GenerationResult` / `EvaluationResult` / `ImageRecord` 全部类型定义）
- [ ] 编写 `backend/agent/checkpointer.py`（初始化 `langgraph-checkpoint-postgres`，连接 PostgreSQL）
- [ ] 编写 `backend/agent/graph.py` 骨架（ReAct 循环，`agent` 节点 + `tools_condition`，`recursion_limit=25`，`interrupt_before=["agent"]`，暂时不挂工具）
- [ ] 验证空 Graph 可以正常 `ainvoke`

> ⚠️ 注意：`langgraph-checkpoint-postgres` 需要在 FastAPI 启动时初始化（`lifespan` 事件），不能在请求时临时创建连接。

**C-3 信息收集工具**

- [ ] 编写 `agent/prompts.py`（`collect_info_system` / `analyze_image_system` / `lookup_style_system` 三个 Prompt 函数）
- [ ] 编写 `agent/tools/image_analysis.py`（`analyze_reference_image`：调用 `LLMClient.ainvoke_with_vision`，返回 `ReferenceImageAnalysis`）
- [ ] 编写 `agent/tools/style_lookup.py`（`lookup_style_keywords`：从 `prompt_templates.py` 查询风格关键词，纯本地查询，无 LLM 调用）
- [ ] 将两个工具挂入 Graph，手动测试工具调用

**C-4 Prompt 构建与图像生成工具**

- [ ] 补充 `agent/prompts.py`（`enhance_prompt_system` / `refine_prompt_system`）
- [ ] 编写 `agent/tools/prompt_builder.py`（`enhance_prompt`：调用 LLM 生成结构化提示词；`refine_prompt`：根据 `EvaluationResult` 各维度分数针对性修正）
- [ ] 编写 `agent/tools/image_generator.py`（`generate_image`：提交 Celery 任务，轮询 Redis，超时计入 `retry_count`，推送 `generation_start` / `generation_done` SSE 事件）
- [ ] 将工具挂入 Graph

> ⚠️ 注意：`generate_image` 工具内部是 async 轮询，需用 `asyncio.sleep` 而非 `time.sleep`，否则会阻塞 FastAPI 事件循环。

> 🧪 测试：`tests/agent/tools/test_prompt_builder.py`
> - `similar_cases=[]` 时 `enhance_prompt` 正常返回，不报错
> - `refine_prompt` 材质分低时输出包含材质相关关键词（可用 mock LLM）

**C-5 评估与重试工具**

- [ ] 补充 `agent/prompts.py`（`evaluate_image_system`，区分有无参考图两套权重说明）
- [ ] 编写 `agent/tools/image_evaluator.py`（`evaluate_generated_image`：调用 VLM 对生成图打分，`reference_images` 为空时用 5 维权重，非空时用 6 维权重，返回 `EvaluationResult`）
- [ ] 在 Graph 中实现重试逻辑（`retry_count < 3` 且 `score < 0.8` 时循环，`retry_count == 3` 时取 `generation_results` 中 score 最高的结果）

> 🧪 测试：`tests/agent/tools/test_image_evaluator.py`
> - `reference_images=[]` 时权重之和为 1.0，不含 `reference_score`
> - `reference_images` 非空时权重之和为 1.0，含 `reference_score`
> - 加权计算结果精度正确

**C-6 SSE 流式输出**

- [ ] 编写 `core/llm/streaming.py`（从 LangGraph `astream_events` 过滤，映射到 7 种 SSE 事件类型，`summarize_tool_output` 转用户友好摘要）
- [ ] 编写 `backend/api/routes/chat.py`（`POST /api/chat/sessions/{id}/messages`，SSE 响应，事件 id 递增，支持 `Last-Event-ID` 断线重连）
- [ ] 加最外层 `@observe(name="agent:turn")` Trace

> ⚠️ 注意：FastAPI SSE 响应需设置 `Content-Type: text/event-stream` 和 `Cache-Control: no-cache`，并在每个事件后 flush。断线重连时从 `Last-Event-ID` 对应的事件之后续传，需在内存或 Redis 中短暂缓存最近的事件序列（TTL 60s 即可）。

**C-7 Langfuse 集成**

- [ ] 在 `backend/main.py` 初始化 Langfuse（从 dashboard.yaml 读取 host / public_key / secret_key）
- [ ] 所有工具函数加 `@observe()` 装饰
- [ ] `agent` 节点函数加 `@observe(name="node:agent")`
- [ ] 节点内用 `langfuse_context.update_current_observation()` 关联 LLM 输入输出
- [ ] 验证 Langfuse UI 中能看到完整 Trace 树

---

### D 阶段：image-rag-mcp 服务

> 目标：图库存储和检索功能完整可用，Agent 可以调用 MCP 工具存图和搜图。

**D-1 MCP 服务骨架与存储初始化**

- [ ] 编写 `image-rag-mcp/server.py`（FastMCP stdio 入口，注册工具）
- [ ] 初始化 Milvus Collection（`caption_vector` 1536 维 + `image_vector` 512 维，标量字段 style / building_type / image_url）
- [ ] 创建 PostgreSQL `image_library` 表
- [ ] 编写 `image-rag-mcp/core/pg_client.py`（`image_library` 表 CRUD，`image_id` 作为 Milvus 关联键）
- [ ] 编写 `image-rag-mcp/core/milvus_client.py`（insert / search 封装）

> ⚠️ 注意：Milvus Collection 创建时需指定 `index_type`（推荐 `HNSW`）和 `metric_type`（`IP` 内积或 `L2`），建议用 `IP` + 归一化向量，检索结果更稳定。

**D-2 VLM Caption 与向量化**

- [ ] 编写 `image-rag-mcp/core/vlm_caption.py`（读取 dashboard.yaml 中的 LLM 配置，调用 `ainvoke_with_vision` 生成图片描述）
- [ ] 编写 `image-rag-mcp/core/clip_encoder.py`（加载 CLIP 模型，图片 URL → 512 维向量）

> ⚠️ 注意：CLIP 模型首次加载较慢，建议在 MCP 服务启动时预加载，不要在每次工具调用时重新加载。

**D-3 MCP 工具实现**

- [ ] 编写 `image-rag-mcp/tools/store.py`（`store_generated_image`：VLM caption → embedding → 存 Milvus + PostgreSQL）
- [ ] 编写 `image-rag-mcp/tools/search.py`（`search_by_text`：文字 → embedding → Milvus 检索；`search_by_image`：图片 → CLIP → Milvus 检索）
- [ ] 编写 `image-rag-mcp/tools/retrieve.py`（`get_image_by_id`：按 image_id 查 PostgreSQL）

**D-4 Agent 侧接入**

- [ ] 编写 `agent/tools/store_to_library.py`（`store_to_library`：通过 `langchain-mcp-adapters` 调用 MCP `store_generated_image`）
- [ ] 编写 `agent/tools/search_library.py`（`search_similar_cases`：通过 MCP `search_by_text` 检索，结果存入 `AgentState.similar_cases`）
- [ ] 在 `agent/graph.py` 初始化时启动 `MultiServerMCPClient`，将 MCP 工具合并进工具列表
- [ ] 端到端测试：存一张图 → 检索 → 验证结果返回正确

---

### E 阶段：前端对接与联调

> 目标：前端完整对接后端，完整走通用户对话 → 上传参考图 → 生成图片 → 存入图库的全流程。

**E-1 对话界面**

- [ ] 编写 `hooks/useSSE.ts`（消费 SSE 流，按事件类型分发：`text_delta` 追加文字、`tool_start/end` 显示状态条、`generation_start/done` 显示生成卡片）
- [ ] 编写 `components/chat/ChatPanel.tsx` / `MessageList.tsx` / `InputBar.tsx`
- [ ] 编写 `store/chatStore.ts`（Zustand，管理 messages / sessionId / generationStatus）
- [ ] 验证纯文字对话流程正常

**E-2 参考图上传**

- [ ] 编写 `components/chat/ImageUploader.tsx`（拖拽或点击上传，调用 `POST /api/upload`，预览缩略图）
- [ ] 上传成功后将 `url` 附在下一条消息发送给 Agent
- [ ] 验证 Agent 收到图片后触发 `analyze_reference_image`

**E-3 生成结果展示**

- [ ] 编写 `components/gallery/ResultGallery.tsx`（展示历史生成结果，支持查看大图）
- [ ] 编写 `hooks/useImageGeneration.ts`（监听 `generation_done` 事件，更新图片列表）
- [ ] 生成完成后展示"是否存入图库"确认按钮，用户确认后发消息触发 `store_to_library`

**E-4 全流程联调**

- [ ] 完整走通：创建会话 → 多轮对话 → 上传参考图 → 触发生成 → 评估重试 → 展示结果 → 存入图库 → 检索相似案例
- [ ] 验证断线重连（关闭 SSE 连接后重新连接，从断点续传）
- [ ] 验证用户中断（生成中途发新消息，Agent 正确感知并重新决策）

---

## 当前状态

**阶段**：架构设计完成，尚未开始编码

**最近决策记录**：
- 2026-04-30：确定使用 LangGraph 搭建 Agent，替代原方案中的自定义 architect_agent.py
- 2026-04-30：记忆系统分为短期/工作/参考图/长期四个层次
- 2026-04-30：图像生成使用 Celery 异步队列，前端轮询状态
- 2026-04-30：图像生成服务选用云端 API，支持三个平台：阿里云百炼（Qwen）、火山引擎豆包、OpenRouter
- 2026-04-30：不做用户登录系统，改为 Dashboard 页面供用户配置模型和 API Key
- 2026-04-30：LangGraph checkpointer 使用 PostgreSQL（langgraph-checkpoint-postgres）
- 2026-04-30：Langfuse 使用 Docker 自部署，纳入 docker-compose.yml
- 2026-04-30：Dashboard API Key 明文存 DB（dashboard_config 表），内部工具无需加密
- 2026-04-30：新增 image-rag-mcp 独立服务，通过 stdio 与 Agent 通信
- 2026-04-30：向量存储策略：caption_vector（文字检索）+ image_vector（以图搜图）双向量存 Milvus，提示词和元数据存 PostgreSQL image_library 表，通过 image_id 关联
- 2026-04-30：VLM Caption 复用对话 LLM API（从 dashboard_config 读取配置），不单独部署模型
- 2026-04-30：Agent 改为 ReAct 循环模式，原固定节点（check_completeness 等）改为工具调用
- 2026-04-30：工具集确定为 8 个，分信息收集/生成执行/生成后处理三组；重试上限 3 次
- 2026-04-30：AgentState 新增 generation_results、retry_count、last_evaluation、similar_cases 字段
- 2026-04-30：ReAct 循环边界：重试上限 3 次、工具调用总步数 25（recursion_limit）、用户中断（interrupt_before）、评估兜底返回最高分结果
- 2026-04-30：SSE 事件协议确定 7 种事件类型；工具状态半透明展示；generate_image 解耦推送；支持 Last-Event-ID 断线重连
- 2026-04-30：图像生成平台统一接口采用抽象工厂模式 + httpx；三平台格式差异封装在各客户端内，工具层只调用统一调度器
- 2026-04-30：对话模型改为 VLM，支持百炼（Qwen3-VL）和火山引擎豆包 VLM，Dashboard 可切换；LLM 层同样采用工厂模式，平台范围限定为百炼和火山引擎
- 2026-04-30：MCP 框架选用 FastMCP（mcp.server.fastmcp，官方 mcp 库内置）
- 2026-04-30：Embedding 模型选用百炼 text-embedding-v3（云端调用），独立放在 image-rag-mcp/core/embedding/ 文件夹，不与 LLM 混放；pg_client.py 负责 image_library 表 CRUD，通过 image_id 关联 Milvus 向量

---



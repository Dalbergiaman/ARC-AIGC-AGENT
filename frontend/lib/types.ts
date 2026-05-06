export type LLMConfig = {
  provider: string;
  model: string;
  api_key: string;
};

export type ImageProviderConfig = {
  provider: string;
  model: string;
  api_key: string;
};

export type EmbeddingConfig = {
  provider: string;
  api_key: string;
};

export type LangfuseConfig = {
  host: string;
  public_key: string;
  secret_key: string;
};

export type DashboardConfig = {
  llm: LLMConfig;
  image_provider: ImageProviderConfig;
  embedding: EmbeddingConfig;
  langfuse: LangfuseConfig;
};

export type DashboardConfigPatch = {
  llm?: Partial<LLMConfig>;
  image_provider?: Partial<ImageProviderConfig>;
  embedding?: Partial<EmbeddingConfig>;
  langfuse?: Partial<LangfuseConfig>;
};

export type LLMProviderOption = {
  id: string;
  label: string;
  models: string[];
};

export type ImageProviderOption = {
  id: string;
  label: string;
  models: string[];
};

export type DashboardProviders = {
  llm: LLMProviderOption[];
  image_provider: ImageProviderOption[];
  embedding: LLMProviderOption[];
};

export type SessionResponse = {
  id: string;
  design_state: Record<string, unknown> | null;
  created_at?: string;
};

export type SessionDetailResponse = SessionResponse & {
  messages: ChatMessage[];
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt?: string;
};

export type SubmitMessageResponse = {
  stream_id: string;
};

export type GenerationPreview = {
  taskId: string;
  imageUrl: string;
  runId?: string;
};

export type ToolStatus = {
  tool: string;
  summary: string;
};

export type SSEEventPayloadMap = {
  text_delta: { content: string };
  tool_start: { tool: string; input?: Record<string, unknown>; summary?: string };
  tool_end: { tool: string; summary: string };
  generation_start: { task_id: string; run_id?: string };
  generation_done: { task_id: string; image_url: string; run_id?: string };
  error: { code: string; message: string };
  done: { finish_reason: "stop" | "max_retries" | "interrupted" };
};

export type SSEEventType = keyof SSEEventPayloadMap;

export type WorkspaceTab = "prompt" | "images";

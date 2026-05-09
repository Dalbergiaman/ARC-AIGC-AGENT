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
  title: string;
  design_state: Record<string, unknown> | null;
  workspace_state?: PromptDraft | null;
  created_at?: string;
};

export type SessionDetailResponse = SessionResponse & {
  messages: ChatMessage[];
  reference_images?: SessionReferenceImage[];
  generation_tasks?: SessionGenerationTask[];
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
  imageUrl?: string | null;
  runId?: string;
  score?: number | null;
  provider?: string | null;
  status?: string;
  prompt?: string;
  negativePrompt?: string | null;
  rawResponse?: Record<string, unknown> | null;
};

export type StyleTemplate = {
  style: string;
  positive: string[];
  negative: string[];
  mood: string;
  description: string;
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
  prompt_update: {
    keywords: Record<string, string>;
    llm_description: string;
    custom_description: string;
    negative_prompt: string;
    prompt_template: StyleTemplate | null;
    source: "agent_node" | "enhance_prompt" | "refine_prompt";
  };
  error: { code: string; message: string };
  done: { finish_reason: "stop" | "max_retries" | "interrupted" };
};

export type SSEEventType = keyof SSEEventPayloadMap;

export type WorkspaceTab = "prompt" | "images";

export type ReferenceIntent =
  | "composition"
  | "color"
  | "style"
  | "material"
  | "lighting"
  | "surroundings"
  | "other";

export type ReferenceImageDraft = {
  fileId: string;
  url: string;
  intent: ReferenceIntent;
  note?: string;
  uploading?: boolean;
  error?: string;
  sent?: boolean;  // true after the image has been submitted in a message
  analysis?: Record<string, unknown> | null;
};

export type ControlImageDraft = {
  fileId: string;
  url: string;
  note?: string;
  uploading?: boolean;
  error?: string;
  sent?: boolean;
};

export type AnnotatedImageDraft = {
  fileId: string;
  url: string;
  note?: string;
  uploading?: boolean;
  error?: string;
  sent?: boolean;
};

export type SessionReferenceImage = {
  id: string;
  file_id: string;
  url: string;
  analysis?: {
    image_url?: string;
    building_type?: string;
    style?: string;
    facade_material?: string;
    lighting?: string;
    viewpoint?: string;
    color_palette?: string;
    description?: string;
    reference_intent?: ReferenceIntent;
    intent_note?: string;
    file_id?: string;
    intent?: ReferenceIntent;
    note?: string;
    sent?: boolean;
  } | null;
  created_at?: string;
};

export type SessionGenerationTask = {
  id: string;
  task_id?: string | null;
  prompt: string;
  negative_prompt?: string | null;
  provider?: string | null;
  image_url?: string | null;
  status: string;
  score?: number | null;
  raw_response?: Record<string, unknown> | null;
  created_at?: string;
};

export type SubmitMessagePayload = {
  content: string;
  reference_images?: Array<{
    file_id: string;
    url: string;
    intent: ReferenceIntent;
    note?: string;
  }>;
  control_image?: {
    file_id: string;
    url: string;
    note?: string;
  } | null;
  annotated_image?: {
    file_id: string;
    url: string;
    note?: string;
  } | null;
  workspace?: {
    keywords?: Record<string, string>;
    llm_description: string;
    custom_description: string;
    negative_prompt: string;
    prompt_template?: StyleTemplate | null;
  };
};

export type PromptDraft = {
  keywords: Record<string, string>;
  llm_description: string;
  custom_description: string;
  negative_prompt: string;
  prompt_template: StyleTemplate | null;
};

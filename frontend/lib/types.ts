export type LLMConfig = {
  provider: string;
  model: string;
  api_key: string;
};

export type ImageProviderConfig = {
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
  langfuse: LangfuseConfig;
};

export type DashboardConfigPatch = {
  llm?: Partial<LLMConfig>;
  image_provider?: Partial<ImageProviderConfig>;
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
};

export type DashboardProviders = {
  llm: LLMProviderOption[];
  image_provider: ImageProviderOption[];
};

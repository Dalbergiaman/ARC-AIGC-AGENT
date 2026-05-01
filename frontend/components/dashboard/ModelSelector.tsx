import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { DashboardConfig, DashboardConfigPatch, DashboardProviders } from "@/lib/types";

type Props = {
  config: DashboardConfig;
  providers: DashboardProviders;
  onPatch: (patch: DashboardConfigPatch) => void;
};

export function ModelSelector({ config, providers, onPatch }: Props) {
  const [showKey, setShowKey] = useState(false);
  const llmProviders = providers.llm;
  const currentProvider = llmProviders.find((item) => item.id === config.llm.provider) ?? llmProviders[0];
  const availableModels = currentProvider?.models ?? [];

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-semibold">对话模型</h2>
      <div className="grid gap-3">
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Provider</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              value={config.llm.provider}
              onChange={(event) => {
                const provider = event.target.value;
                const nextProvider = llmProviders.find((item) => item.id === provider);
                const nextModel = nextProvider?.models[0] ?? "";
                onPatch({ llm: { provider, model: nextModel } });
              }}
            >
              {llmProviders.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-sm">
            <span className="text-muted-foreground">Model</span>
            <select
              className="h-9 w-full rounded-md border bg-background px-3 text-sm"
              value={config.llm.model}
              onChange={(event) => {
                onPatch({ llm: { model: event.target.value } });
              }}
            >
              {availableModels.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">LLM API Key</span>
          <div className="relative">
            <input
              className="h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm"
              type={showKey ? "text" : "password"}
              value={config.llm.api_key}
              onChange={(event) => {
                onPatch({ llm: { api_key: event.target.value } });
              }}
            />
            <button
              type="button"
              onClick={() => setShowKey((prev) => !prev)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showKey ? "隐藏密钥" : "显示密钥"}
            >
              {showKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </label>
      </div>
    </section>
  );
}

import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

import type { DashboardConfig, DashboardConfigPatch, DashboardProviders } from "@/lib/types";

type Props = {
  config: DashboardConfig;
  providers: DashboardProviders;
  onPatch: (patch: DashboardConfigPatch) => void;
};

export function EmbeddingConfig({ config, providers, onPatch }: Props) {
  const [showKey, setShowKey] = useState(false);
  const embeddingProviders = providers.embedding;
  const currentProvider =
    embeddingProviders.find((item) => item.id === config.embedding.provider) ?? embeddingProviders[0];

  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-semibold">Embedding</h2>
      <div className="grid gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Provider</span>
          <select
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            value={config.embedding.provider}
            onChange={(event) => {
              onPatch({ embedding: { provider: event.target.value } });
            }}
          >
            {embeddingProviders.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        {currentProvider?.models?.length ? (
          <div className="rounded-md border border-dashed px-3 py-2 text-xs text-muted-foreground">
            Models: {currentProvider.models.join(", ")}
          </div>
        ) : null}

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Embedding API Key</span>
          <div className="relative">
            <input
              className="h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm"
              type={showKey ? "text" : "password"}
              value={config.embedding.api_key}
              onChange={(event) => {
                onPatch({ embedding: { api_key: event.target.value } });
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

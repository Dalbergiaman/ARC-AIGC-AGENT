import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { DashboardConfig, DashboardConfigPatch, DashboardProviders } from "@/lib/types";

type Props = {
  config: DashboardConfig;
  providers: DashboardProviders;
  onPatch: (patch: DashboardConfigPatch) => void;
};

export function ImageProviderConfig({ config, providers, onPatch }: Props) {
  const [showKey, setShowKey] = useState(false);
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-semibold">图像生成平台</h2>
      <div className="grid gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Provider</span>
          <select
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            value={config.image_provider.provider}
            onChange={(event) => {
              onPatch({ image_provider: { provider: event.target.value } });
            }}
          >
            {providers.image_provider.map((option) => (
              <option key={option.id} value={option.id}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Image Provider API Key</span>
          <div className="relative">
            <input
              className="h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm"
              type={showKey ? "text" : "password"}
              value={config.image_provider.api_key}
              onChange={(event) => {
                onPatch({ image_provider: { api_key: event.target.value } });
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

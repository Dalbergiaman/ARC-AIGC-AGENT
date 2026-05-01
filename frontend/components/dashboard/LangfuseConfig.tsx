import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
import type { DashboardConfig, DashboardConfigPatch } from "@/lib/types";

type Props = {
  config: DashboardConfig;
  onPatch: (patch: DashboardConfigPatch) => void;
};

export function LangfuseConfig({ config, onPatch }: Props) {
  const [showPublicKey, setShowPublicKey] = useState(false);
  const [showSecretKey, setShowSecretKey] = useState(false);
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-semibold">Langfuse</h2>
      <div className="grid gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Host</span>
          <input
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            type="text"
            value={config.langfuse.host}
            onChange={(event) => {
              onPatch({ langfuse: { host: event.target.value } });
            }}
          />
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Public Key</span>
          <div className="relative">
            <input
              className="h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm"
              type={showPublicKey ? "text" : "password"}
              value={config.langfuse.public_key}
              onChange={(event) => {
                onPatch({ langfuse: { public_key: event.target.value } });
              }}
            />
            <button
              type="button"
              onClick={() => setShowPublicKey((prev) => !prev)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showPublicKey ? "隐藏密钥" : "显示密钥"}
            >
              {showPublicKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Secret Key</span>
          <div className="relative">
            <input
              className="h-9 w-full rounded-md border bg-background px-3 pr-9 text-sm"
              type={showSecretKey ? "text" : "password"}
              value={config.langfuse.secret_key}
              onChange={(event) => {
                onPatch({ langfuse: { secret_key: event.target.value } });
              }}
            />
            <button
              type="button"
              onClick={() => setShowSecretKey((prev) => !prev)}
              className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label={showSecretKey ? "隐藏密钥" : "显示密钥"}
            >
              {showSecretKey ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
        </label>
      </div>
    </section>
  );
}

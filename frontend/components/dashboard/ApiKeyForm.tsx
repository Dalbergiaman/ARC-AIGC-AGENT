import type { DashboardConfig, DashboardConfigPatch } from "@/lib/types";

type Props = {
  config: DashboardConfig;
  onPatch: (patch: DashboardConfigPatch) => void;
};

export function ApiKeyForm({ config, onPatch }: Props) {
  return (
    <section className="space-y-3 rounded-lg border p-4">
      <h2 className="text-sm font-semibold">API Key</h2>
      <div className="grid gap-3">
        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">LLM API Key</span>
          <input
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            type="text"
            value={config.llm.api_key}
            onChange={(event) => {
              onPatch({ llm: { api_key: event.target.value } });
            }}
          />
        </label>

        <label className="space-y-1 text-sm">
          <span className="text-muted-foreground">Image Provider API Key</span>
          <input
            className="h-9 w-full rounded-md border bg-background px-3 text-sm"
            type="text"
            value={config.image_provider.api_key}
            onChange={(event) => {
              onPatch({ image_provider: { api_key: event.target.value } });
            }}
          />
        </label>
      </div>
    </section>
  );
}

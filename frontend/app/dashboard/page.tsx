"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { updateDashboardConfig, getDashboardConfig, getDashboardProviders } from "@/lib/api";
import type { DashboardConfig, DashboardConfigPatch, DashboardProviders } from "@/lib/types";
import { ImageProviderConfig } from "@/components/dashboard/ImageProviderConfig";
import { LangfuseConfig } from "@/components/dashboard/LangfuseConfig";
import { ModelSelector } from "@/components/dashboard/ModelSelector";
import { Button } from "@/components/ui/button";

function mergePatch(config: DashboardConfig, patch: DashboardConfigPatch): DashboardConfig {
  return {
    ...config,
    llm: { ...config.llm, ...(patch.llm ?? {}) },
    image_provider: { ...config.image_provider, ...(patch.image_provider ?? {}) },
    langfuse: { ...config.langfuse, ...(patch.langfuse ?? {}) },
  };
}

type SettingsTab = "model" | "langfuse";

export default function DashboardPage() {
  const [config, setConfig] = useState<DashboardConfig | null>(null);
  const [providers, setProviders] = useState<DashboardProviders | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<SettingsTab>("model");

  useEffect(() => {
    let active = true;

    async function load() {
      try {
        setLoading(true);
        setError(null);
        const [nextConfig, nextProviders] = await Promise.all([
          getDashboardConfig(),
          getDashboardProviders(),
        ]);
        if (!active) {
          return;
        }
        setConfig(nextConfig);
        setProviders(nextProviders);
      } catch (loadError) {
        if (!active) {
          return;
        }
        setError(loadError instanceof Error ? loadError.message : "加载失败");
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    }

    load();
    return () => {
      active = false;
    };
  }, []);

  const canRenderForm = useMemo(() => Boolean(config && providers), [config, providers]);

  const handlePatch = (patch: DashboardConfigPatch) => {
    setConfig((prev) => (prev ? mergePatch(prev, patch) : prev));
  };

  const handleSave = async () => {
    if (!config) {
      return;
    }
    try {
      setSaving(true);
      setError(null);
      const updated = await updateDashboardConfig(config);
      setConfig(updated);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-1 flex-col">
      <header className="flex items-center justify-between border-b px-4 py-3">
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-md border px-2 py-1 text-sm text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            &lt;
          </Link>
          <h1 className="text-base font-semibold">Dashboard</h1>
        </div>
        <Button onClick={handleSave} disabled={loading || saving || !canRenderForm}>
          {saving ? "保存中..." : "保存配置"}
        </Button>
      </header>

      <main className="flex flex-1 p-4">
        <aside className="w-56 shrink-0 border-r pr-4">
          <nav className="space-y-1">
            <button
              type="button"
              onClick={() => setActiveTab("model")}
              className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                activeTab === "model" ? "bg-accent font-medium" : "text-muted-foreground"
              }`}
            >
              Model Config
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("langfuse")}
              className={`w-full rounded-md px-3 py-2 text-left text-sm ${
                activeTab === "langfuse" ? "bg-accent font-medium" : "text-muted-foreground"
              }`}
            >
              Langfuse
            </button>
          </nav>
        </aside>

        <section className="min-w-0 flex-1 pl-4">
          {loading && <p className="text-sm text-muted-foreground">正在加载配置...</p>}
          {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

          {canRenderForm && config && providers && activeTab === "model" && (
            <div className="grid gap-4">
              <ModelSelector config={config} providers={providers} onPatch={handlePatch} />
              <ImageProviderConfig config={config} providers={providers} onPatch={handlePatch} />
            </div>
          )}

          {canRenderForm && config && activeTab === "langfuse" && (
            <LangfuseConfig config={config} onPatch={handlePatch} />
          )}
        </section>
      </main>
    </div>
  );
}

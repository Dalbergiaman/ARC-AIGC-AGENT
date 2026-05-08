import { create } from "zustand";
import { persist } from "zustand/middleware";

import type { ReferenceImageDraft, WorkspaceTab } from "@/lib/types";

const MIN_WORKSPACE_RATIO = 0.22;
const MAX_WORKSPACE_RATIO = 0.65;
const DEFAULT_WORKSPACE_RATIO = 0.28;

type WorkspaceStore = {
  // UI layout (not persisted)
  sidebarCollapsed: boolean;
  activeTab: WorkspaceTab;
  workspaceCollapsed: boolean;
  workspaceWidthRatio: number;
  // Prompt drafts (not persisted — synced from Agent in E-3)
  promptDraft: string;
  negativePromptDraft: string;
  // Reference images keyed by sessionId (persisted to localStorage)
  referenceImagesBySession: Record<string, ReferenceImageDraft[]>;
  // Layout actions
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  setWorkspaceCollapsed: (collapsed: boolean) => void;
  toggleWorkspace: () => void;
  setWorkspaceWidthRatio: (ratio: number) => void;
  // Prompt actions
  setPromptDraft: (prompt: string) => void;
  setNegativePromptDraft: (prompt: string) => void;
  // Reference image actions (all scoped to a sessionId)
  getReferenceImages: (sessionId: string) => ReferenceImageDraft[];
  addReferenceImage: (sessionId: string, img: ReferenceImageDraft) => void;
  updateReferenceImage: (sessionId: string, fileId: string, patch: Partial<ReferenceImageDraft>) => void;
  removeReferenceImage: (sessionId: string, fileId: string) => void;
  clearSessionReferenceImages: (sessionId: string) => void;
};

function clampWorkspaceWidthRatio(ratio: number): number {
  return Math.min(MAX_WORKSPACE_RATIO, Math.max(MIN_WORKSPACE_RATIO, ratio));
}

export const useWorkspaceStore = create<WorkspaceStore>()(
  persist(
    (set, get) => ({
      sidebarCollapsed: false,
      activeTab: "prompt",
      workspaceCollapsed: false,
      workspaceWidthRatio: DEFAULT_WORKSPACE_RATIO,
      promptDraft: "",
      negativePromptDraft: "",
      referenceImagesBySession: {},

      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setActiveTab: (activeTab) => set({ activeTab }),
      setWorkspaceCollapsed: (workspaceCollapsed) => set({ workspaceCollapsed }),
      toggleWorkspace: () => set((state) => ({ workspaceCollapsed: !state.workspaceCollapsed })),
      setWorkspaceWidthRatio: (workspaceWidthRatio) =>
        set({ workspaceWidthRatio: clampWorkspaceWidthRatio(workspaceWidthRatio) }),

      setPromptDraft: (promptDraft) => set({ promptDraft }),
      setNegativePromptDraft: (negativePromptDraft) => set({ negativePromptDraft }),

      getReferenceImages: (sessionId) =>
        get().referenceImagesBySession[sessionId] ?? [],

      addReferenceImage: (sessionId, img) =>
        set((state) => ({
          referenceImagesBySession: {
            ...state.referenceImagesBySession,
            [sessionId]: [...(state.referenceImagesBySession[sessionId] ?? []), img],
          },
        })),

      updateReferenceImage: (sessionId, fileId, patch) =>
        set((state) => ({
          referenceImagesBySession: {
            ...state.referenceImagesBySession,
            [sessionId]: (state.referenceImagesBySession[sessionId] ?? []).map((img) =>
              img.fileId === fileId ? { ...img, ...patch } : img,
            ),
          },
        })),

      removeReferenceImage: (sessionId, fileId) =>
        set((state) => ({
          referenceImagesBySession: {
            ...state.referenceImagesBySession,
            [sessionId]: (state.referenceImagesBySession[sessionId] ?? []).filter(
              (img) => img.fileId !== fileId,
            ),
          },
        })),

      clearSessionReferenceImages: (sessionId) =>
        set((state) => ({
          referenceImagesBySession: {
            ...state.referenceImagesBySession,
            [sessionId]: [],
          },
        })),
    }),
    {
      name: "workspace-store",
      // Only persist reference images — layout and prompt drafts are transient
      partialize: (state) => ({
        referenceImagesBySession: state.referenceImagesBySession,
      }),
    },
  ),
);

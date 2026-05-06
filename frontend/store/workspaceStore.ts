import { create } from "zustand";

import type { WorkspaceTab } from "@/lib/types";

const MIN_WORKSPACE_RATIO = 0.22;
const MAX_WORKSPACE_RATIO = 0.65;
const DEFAULT_WORKSPACE_RATIO = 0.28;

type WorkspaceStore = {
  sidebarCollapsed: boolean;
  activeTab: WorkspaceTab;
  workspaceCollapsed: boolean;
  workspaceWidthRatio: number;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  setWorkspaceCollapsed: (collapsed: boolean) => void;
  toggleWorkspace: () => void;
  setWorkspaceWidthRatio: (ratio: number) => void;
};

function clampWorkspaceWidthRatio(ratio: number): number {
  return Math.min(MAX_WORKSPACE_RATIO, Math.max(MIN_WORKSPACE_RATIO, ratio));
}

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  sidebarCollapsed: false,
  activeTab: "prompt",
  workspaceCollapsed: false,
  workspaceWidthRatio: DEFAULT_WORKSPACE_RATIO,
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setWorkspaceCollapsed: (workspaceCollapsed) => set({ workspaceCollapsed }),
  toggleWorkspace: () => set((state) => ({ workspaceCollapsed: !state.workspaceCollapsed })),
  setWorkspaceWidthRatio: (workspaceWidthRatio) =>
    set({ workspaceWidthRatio: clampWorkspaceWidthRatio(workspaceWidthRatio) }),
}));

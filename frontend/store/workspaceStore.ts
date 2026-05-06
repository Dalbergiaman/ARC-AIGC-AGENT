import { create } from "zustand";

import type { WorkspaceTab } from "@/lib/types";

const MIN_WORKSPACE_WIDTH = 280;
const MAX_WORKSPACE_WIDTH = 760;
const DEFAULT_WORKSPACE_WIDTH = 320;

type WorkspaceStore = {
  sidebarCollapsed: boolean;
  activeTab: WorkspaceTab;
  workspaceCollapsed: boolean;
  workspaceWidth: number;
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  setWorkspaceCollapsed: (collapsed: boolean) => void;
  toggleWorkspace: () => void;
  setWorkspaceWidth: (width: number) => void;
};

function clampWorkspaceWidth(width: number): number {
  return Math.min(MAX_WORKSPACE_WIDTH, Math.max(MIN_WORKSPACE_WIDTH, width));
}

export const useWorkspaceStore = create<WorkspaceStore>((set) => ({
  sidebarCollapsed: false,
  activeTab: "prompt",
  workspaceCollapsed: false,
  workspaceWidth: DEFAULT_WORKSPACE_WIDTH,
  setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
  setActiveTab: (activeTab) => set({ activeTab }),
  setWorkspaceCollapsed: (workspaceCollapsed) => set({ workspaceCollapsed }),
  toggleWorkspace: () => set((state) => ({ workspaceCollapsed: !state.workspaceCollapsed })),
  setWorkspaceWidth: (workspaceWidth) =>
    set({ workspaceWidth: clampWorkspaceWidth(workspaceWidth) }),
}));

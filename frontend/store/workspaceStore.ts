import { create } from "zustand";
import { persist } from "zustand/middleware";

import type {
  AnnotatedImageDraft,
  ControlImageDraft,
  PromptDraft,
  RagImageState,
  ReferenceImageDraft,
  StyleTemplate,
  WorkspaceTab,
} from "@/lib/types";

const MIN_WORKSPACE_RATIO = 0.22;
const MAX_WORKSPACE_RATIO = 0.65;
const DEFAULT_WORKSPACE_RATIO = 0.28;

function createEmptyPromptDraft(): PromptDraft {
  return {
    keywords: {},
    llm_description: "",
    custom_description: "",
    negative_prompt: "",
    prompt_template: null,
  };
}

type WorkspaceStore = {
  // UI layout (not persisted)
  sidebarCollapsed: boolean;
  activeTab: WorkspaceTab;
  workspaceCollapsed: boolean;
  workspaceWidthRatio: number;
  // Active prompt draft for the current session
  promptDraft: PromptDraft;
  // Session-scoped workspace state persisted to localStorage
  controlImageBySession: Record<string, ControlImageDraft | null>;
  annotatedImageBySession: Record<string, AnnotatedImageDraft | null>;
  ragImageBySession: Record<string, RagImageState | null>;
  referenceImagesBySession: Record<string, ReferenceImageDraft[]>;
  promptDraftBySession: Record<string, PromptDraft>;
  promptTemplateBySession: Record<string, StyleTemplate | null>;
  // Layout actions
  setSidebarCollapsed: (collapsed: boolean) => void;
  toggleSidebar: () => void;
  setActiveTab: (tab: WorkspaceTab) => void;
  setWorkspaceCollapsed: (collapsed: boolean) => void;
  toggleWorkspace: () => void;
  setWorkspaceWidthRatio: (ratio: number) => void;
  // Prompt actions
  setPromptDraft: (draft: Partial<PromptDraft>) => void;
  setPromptDraftField: <K extends keyof PromptDraft>(field: K, value: PromptDraft[K]) => void;
  getPromptDraft: (sessionId: string) => PromptDraft;
  setSessionPromptDraft: (sessionId: string, draft: Partial<PromptDraft>) => void;
  setSessionPromptDraftField: <K extends keyof PromptDraft>(
    sessionId: string,
    field: K,
    value: PromptDraft[K],
  ) => void;
  setSessionPromptTemplate: (sessionId: string, promptTemplate: StyleTemplate | null) => void;
  // Reference image actions (all scoped to a sessionId)
  getControlImage: (sessionId: string) => ControlImageDraft | null;
  setControlImage: (sessionId: string, img: ControlImageDraft | null) => void;
  updateControlImage: (sessionId: string, patch: Partial<ControlImageDraft>) => void;
  removeControlImage: (sessionId: string) => void;
  getAnnotatedImage: (sessionId: string) => AnnotatedImageDraft | null;
  setAnnotatedImage: (sessionId: string, img: AnnotatedImageDraft | null) => void;
  updateAnnotatedImage: (sessionId: string, patch: Partial<AnnotatedImageDraft>) => void;
  removeAnnotatedImage: (sessionId: string) => void;
  getReferenceImages: (sessionId: string) => ReferenceImageDraft[];
  addReferenceImage: (sessionId: string, img: ReferenceImageDraft) => void;
  updateReferenceImage: (sessionId: string, fileId: string, patch: Partial<ReferenceImageDraft>) => void;
  removeReferenceImage: (sessionId: string, fileId: string) => void;
  clearSessionReferenceImages: (sessionId: string) => void;
  setSessionReferenceImages: (sessionId: string, images: ReferenceImageDraft[]) => void;
  // RAG image actions
  getRagImage: (sessionId: string) => RagImageState | null;
  setRagImage: (sessionId: string, img: RagImageState | null) => void;
  clearRagImage: (sessionId: string) => void;
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
      promptDraft: createEmptyPromptDraft(),
      controlImageBySession: {},
      annotatedImageBySession: {},
      ragImageBySession: {},
      referenceImagesBySession: {},
      promptDraftBySession: {},
      promptTemplateBySession: {},

      setSidebarCollapsed: (sidebarCollapsed) => set({ sidebarCollapsed }),
      toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
      setActiveTab: (activeTab) => set({ activeTab }),
      setWorkspaceCollapsed: (workspaceCollapsed) => set({ workspaceCollapsed }),
      toggleWorkspace: () => set((state) => ({ workspaceCollapsed: !state.workspaceCollapsed })),
      setWorkspaceWidthRatio: (workspaceWidthRatio) =>
        set({ workspaceWidthRatio: clampWorkspaceWidthRatio(workspaceWidthRatio) }),

      setPromptDraft: (draft) =>
        set((state) => ({
          promptDraft: {
            ...state.promptDraft,
            ...draft,
            keywords: draft.keywords ?? state.promptDraft.keywords,
          },
        })),
      setPromptDraftField: (field, value) =>
        set((state) => ({
          promptDraft: {
            ...state.promptDraft,
            [field]: value,
          },
        })),
      getPromptDraft: (sessionId) =>
        get().promptDraftBySession[sessionId] ?? {
          ...createEmptyPromptDraft(),
          prompt_template: get().promptTemplateBySession[sessionId] ?? null,
        },
      setSessionPromptDraft: (sessionId, draft) =>
        set((state) => {
          const current = state.promptDraftBySession[sessionId] ?? {
            ...createEmptyPromptDraft(),
            prompt_template: state.promptTemplateBySession[sessionId] ?? null,
          };
          const next = {
            ...current,
            ...draft,
            keywords: draft.keywords ?? current.keywords,
          };
          return {
            promptDraft: next,
            promptDraftBySession: {
              ...state.promptDraftBySession,
              [sessionId]: next,
            },
            promptTemplateBySession: {
              ...state.promptTemplateBySession,
              [sessionId]: next.prompt_template,
            },
          };
        }),
      setSessionPromptDraftField: (sessionId, field, value) =>
        set((state) => {
          const current = state.promptDraftBySession[sessionId] ?? {
            ...createEmptyPromptDraft(),
            prompt_template: state.promptTemplateBySession[sessionId] ?? null,
          };
          const next = {
            ...current,
            [field]: value,
          };
          return {
            promptDraft: next,
            promptDraftBySession: {
              ...state.promptDraftBySession,
              [sessionId]: next,
            },
            promptTemplateBySession: {
              ...state.promptTemplateBySession,
              [sessionId]: next.prompt_template,
            },
          };
        }),
      setSessionPromptTemplate: (sessionId, promptTemplate) =>
        set((state) => {
          const current = state.promptDraftBySession[sessionId] ?? {
            ...state.promptDraft,
            prompt_template: state.promptTemplateBySession[sessionId] ?? null,
          };
          const next = {
            ...current,
            prompt_template: promptTemplate,
          };
          return {
            promptDraft: next,
            promptDraftBySession: {
              ...state.promptDraftBySession,
              [sessionId]: next,
            },
            promptTemplateBySession: {
              ...state.promptTemplateBySession,
              [sessionId]: promptTemplate,
            },
          };
        }),

      getControlImage: (sessionId) =>
        get().controlImageBySession[sessionId] ?? null,

      setControlImage: (sessionId, img) =>
        set((state) => ({
          controlImageBySession: {
            ...state.controlImageBySession,
            [sessionId]: img,
          },
        })),

      updateControlImage: (sessionId, patch) =>
        set((state) => {
          const current = state.controlImageBySession[sessionId];
          if (!current) {
            return {};
          }
          return {
            controlImageBySession: {
              ...state.controlImageBySession,
              [sessionId]: { ...current, ...patch },
            },
          };
        }),

      removeControlImage: (sessionId) =>
        set((state) => ({
          controlImageBySession: {
            ...state.controlImageBySession,
            [sessionId]: null,
          },
        })),

      getAnnotatedImage: (sessionId) =>
        get().annotatedImageBySession[sessionId] ?? null,

      setAnnotatedImage: (sessionId, img) =>
        set((state) => ({
          annotatedImageBySession: {
            ...state.annotatedImageBySession,
            [sessionId]: img,
          },
        })),

      updateAnnotatedImage: (sessionId, patch) =>
        set((state) => {
          const current = state.annotatedImageBySession[sessionId];
          if (!current) {
            return {};
          }
          return {
            annotatedImageBySession: {
              ...state.annotatedImageBySession,
              [sessionId]: { ...current, ...patch },
            },
          };
        }),

      removeAnnotatedImage: (sessionId) =>
        set((state) => ({
          annotatedImageBySession: {
            ...state.annotatedImageBySession,
            [sessionId]: null,
          },
        })),

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

      setSessionReferenceImages: (sessionId, images) =>
        set((state) => ({
          referenceImagesBySession: {
            ...state.referenceImagesBySession,
            [sessionId]: images,
          },
        })),

      getRagImage: (sessionId) => get().ragImageBySession[sessionId] ?? null,
      setRagImage: (sessionId, img) =>
        set((state) => ({
          ragImageBySession: { ...state.ragImageBySession, [sessionId]: img },
        })),
      clearRagImage: (sessionId) =>
        set((state) => {
          const { [sessionId]: _, ...rest } = state.ragImageBySession;
          return { ragImageBySession: rest };
        }),
    }),
    {
      name: "workspace-store",
      skipHydration: true,
      // Persist only session-scoped workspace data; layout remains transient.
      partialize: (state) => ({
        controlImageBySession: state.controlImageBySession,
        annotatedImageBySession: state.annotatedImageBySession,
        ragImageBySession: state.ragImageBySession,
        referenceImagesBySession: state.referenceImagesBySession,
        promptDraftBySession: state.promptDraftBySession,
        promptTemplateBySession: state.promptTemplateBySession,
      }),
    },
  ),
);

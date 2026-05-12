import { create } from "zustand";

import type { ChatMessage, GenerationPreview, ToolStatus } from "@/lib/types";

type StreamState = "idle" | "submitting" | "streaming" | "error";

type ChatStore = {
  sessionId: string | null;
  messages: ChatMessage[];
  streamState: StreamState;
  activeToolStatus: ToolStatus | null;
  generationPreviews: GenerationPreview[];
  currentAssistantMessageId: string | null;
  currentAssistantText: string;
  errorMessage: string | null;
  setSessionId: (sessionId: string) => void;
  setMessages: (messages: ChatMessage[]) => void;
  addUserMessage: (content: string) => void;
  beginAssistantMessage: () => void;
  appendAssistantText: (content: string) => void;
  replaceAssistantText: (content: string) => void;
  finalizeAssistantMessage: () => void;
  setStreamState: (state: StreamState) => void;
  setToolStatus: (status: ToolStatus | null) => void;
  upsertGenerationPreview: (preview: GenerationPreview) => void;
  setGenerationPreviews: (previews: GenerationPreview[]) => void;
  failRunningPreviews: () => void;
  setErrorMessage: (message: string | null) => void;
  resetConversation: () => void;
};

function makeMessageId(prefix: string): string {
  return `${prefix}-${crypto.randomUUID()}`;
}

export const useChatStore = create<ChatStore>((set) => ({
  sessionId: null,
  messages: [],
  streamState: "idle",
  activeToolStatus: null,
  generationPreviews: [],
  currentAssistantMessageId: null,
  currentAssistantText: "",
  errorMessage: null,
  setSessionId: (sessionId) => set({ sessionId }),
  setMessages: (messages) =>
    set({
      messages,
      currentAssistantMessageId: null,
      currentAssistantText: "",
      activeToolStatus: null,
      errorMessage: null,
    }),
  addUserMessage: (content) =>
    set((state) => ({
      messages: [
        ...state.messages,
        {
          id: makeMessageId("user"),
          role: "user",
          content,
        },
      ],
      errorMessage: null,
    })),
  beginAssistantMessage: () =>
    set((state) => {
      const id = makeMessageId("assistant");
      return {
        currentAssistantMessageId: id,
        currentAssistantText: "",
        messages: [
          ...state.messages,
          {
            id,
            role: "assistant",
            content: "",
          },
        ],
      };
    }),
  appendAssistantText: (content) =>
    set((state) => {
      if (!state.currentAssistantMessageId) {
        const id = makeMessageId("assistant");
        return {
          currentAssistantMessageId: id,
          currentAssistantText: content,
          messages: [
            ...state.messages,
            {
              id,
              role: "assistant",
              content,
            },
          ],
        };
      }

      const nextText = `${state.currentAssistantText}${content}`;
      return {
        currentAssistantText: nextText,
        messages: state.messages.map((message) =>
          message.id === state.currentAssistantMessageId
            ? { ...message, content: nextText }
            : message,
        ),
      };
    }),
  replaceAssistantText: (content) =>
    set((state) => {
      if (!state.currentAssistantMessageId) return state;
      return {
        currentAssistantText: content,
        messages: state.messages.map((msg) =>
          msg.id === state.currentAssistantMessageId
            ? { ...msg, content }
            : msg,
        ),
      };
    }),
  finalizeAssistantMessage: () =>
    set({
      currentAssistantMessageId: null,
      currentAssistantText: "",
      activeToolStatus: null,
    }),
  setStreamState: (streamState) => set({ streamState }),
  setToolStatus: (activeToolStatus) => set({ activeToolStatus }),
  upsertGenerationPreview: (preview) =>
    set((state) => {
      const existing = state.generationPreviews.findIndex((item) => item.taskId === preview.taskId);
      if (existing === -1) {
        const entry = preview.assistantMessageId
          ? preview
          : { ...preview, assistantMessageId: state.currentAssistantMessageId ?? undefined };
        return { generationPreviews: [...state.generationPreviews, entry] };
      }

      const next = [...state.generationPreviews];
      const merged = { ...next[existing], ...preview };
      // Don't overwrite an existing imageUrl with undefined/null
      if (!preview.imageUrl && next[existing].imageUrl) {
        merged.imageUrl = next[existing].imageUrl;
      }
      next[existing] = merged;
      return { generationPreviews: next };
    }),
  setGenerationPreviews: (generationPreviews) => set({ generationPreviews }),
  failRunningPreviews: () =>
    set((state) => ({
      generationPreviews: state.generationPreviews.map((item) =>
        !item.imageUrl && (!item.status || item.status === "running")
          ? { ...item, status: "failed" }
          : item,
      ),
    })),
  setErrorMessage: (errorMessage) => set({ errorMessage }),
  resetConversation: () =>
    set({
      sessionId: null,
      messages: [],
      streamState: "idle",
      activeToolStatus: null,
      generationPreviews: [],
      currentAssistantMessageId: null,
      currentAssistantText: "",
      errorMessage: null,
    }),
}));

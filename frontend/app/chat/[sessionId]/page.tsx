import { ChatSessionShell } from "@/components/chat/ChatSessionShell";

export default async function ChatPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  return <ChatSessionShell sessionId={sessionId} />;
}

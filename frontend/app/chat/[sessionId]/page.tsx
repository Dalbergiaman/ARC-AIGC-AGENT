export default async function ChatPage({
  params,
}: {
  params: Promise<{ sessionId: string }>;
}) {
  const { sessionId } = await params;

  return (
    <div className="flex flex-1 flex-col">
      <header className="border-b px-4 py-3 text-sm text-muted-foreground">
        会话 {sessionId}
      </header>
      <main className="flex flex-1 flex-col items-center justify-center text-muted-foreground text-sm">
        对话界面（E-1 阶段实现）
      </main>
    </div>
  );
}

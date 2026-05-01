import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">AIGC Agent</h1>
      <p className="text-muted-foreground text-sm">建筑效果图生成系统</p>
      <div className="flex gap-3">
        <Link
          href="/chat/new"
          className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
        >
          开始对话
        </Link>
        <Link
          href="/dashboard"
          className="rounded-md border px-4 py-2 text-sm font-medium hover:bg-accent"
        >
          Dashboard
        </Link>
      </div>
    </div>
  );
}

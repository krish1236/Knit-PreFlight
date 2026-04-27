import { Header } from "@/components/Header";

export default async function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-12">
        <h1 className="text-2xl font-semibold tracking-tight">
          Run {id}
        </h1>
        <p className="mt-3 text-[var(--color-text-muted)]">
          The report card view lands here in the next commit.
        </p>
      </main>
    </div>
  );
}

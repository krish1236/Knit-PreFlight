"use client";

import { useCallback, useEffect, useState } from "react";
import { use } from "react";
import { Header } from "@/components/Header";
import { ReportCard } from "@/components/ReportCard";
import { RunProgress } from "@/components/RunProgress";
import { api, ApiError, type ReportCard as ReportCardData } from "@/lib/api";

export default function RunPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [report, setReport] = useState<ReportCardData | null>(null);
  const [reportError, setReportError] = useState<string | null>(null);

  const loadReport = useCallback(async () => {
    try {
      const r = await api.getReport(id);
      setReport(r);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setReport(null);
        return;
      }
      setReportError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    loadReport();
  }, [loadReport]);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-6 py-10 space-y-8">
        <div>
          <span className="text-xs text-[var(--color-text-muted)] font-mono">
            run {id}
          </span>
          <h1 className="text-2xl font-semibold tracking-tight mt-1">
            Pre-Flight report
          </h1>
        </div>

        {!report && (
          <RunProgress runId={id} onCompleted={loadReport} />
        )}

        {reportError && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/5 p-4 text-sm text-red-200">
            {reportError}
          </div>
        )}

        {report && <ReportCard report={report} />}
      </main>
    </div>
  );
}

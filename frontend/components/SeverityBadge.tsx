import type { Severity } from "@/lib/api";

const styles: Record<Severity, string> = {
  high: "bg-red-500/15 text-red-300 border-red-500/40",
  medium: "bg-amber-500/15 text-amber-200 border-amber-500/40",
  low: "bg-yellow-500/10 text-yellow-200 border-yellow-500/30",
  none: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
};

const labels: Record<Severity, string> = {
  high: "HIGH",
  medium: "MED",
  low: "LOW",
  none: "OK",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[10px] font-semibold tracking-wider ${styles[severity]}`}
    >
      {labels[severity]}
    </span>
  );
}

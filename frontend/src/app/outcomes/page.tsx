"use client";
import { useQuery } from "@tanstack/react-query";
import { ChevronRight, LineChart } from "lucide-react";
import Link from "next/link";
import { ConfidencePill } from "@/components/intel/assessment-cards";
import { DemoBadge } from "@/components/ui/demo-badge";
import { PageHeader } from "@/components/ui/page";
import { ErrorState, Loading } from "@/components/ui/states";
import { api } from "@/lib/api";
import { fmt, fmtBRL, fmtDate } from "@/lib/utils";

export default function OutcomesPage() {
  const q = useQuery({ queryKey: ["outcomes"], queryFn: api.outcomes });
  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader title="Outcomes" subtitle="What each intervention changed, measured against a comparison area." right={<DemoBadge />} />
      <div className="p-6">
        {q.error ? <ErrorState error={q.error} onRetry={() => q.refetch()} /> : !q.data ? <Loading /> : (
          <ul className="space-y-3">
            {q.data.map((o) => (
              <li key={o.id}>
                <Link href={`/outcomes/${o.id}`} className="group flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-4 transition hover:border-slate-300 hover:shadow-sm">
                  <div className="grid size-10 place-items-center rounded-lg bg-emerald-50 text-emerald-700"><LineChart className="size-5" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                      {o.field_name} · {fmtDate(o.executed_at)}
                      {o.user_created ? <DemoBadge label="Simulated post-intervention" /> : <span className="text-violet-600">demo history · previous season</span>}
                    </div>
                    <div className="mt-0.5 truncate text-sm font-semibold text-slate-900">{o.approved_action}</div>
                    <div className="mt-1 text-xs text-slate-600">
                      Zone NDVI {fmt(o.before_value, 2)} → {fmt(o.after_value, 2)} · net gain vs. comparison{" "}
                      <span className="font-semibold text-slate-900">{o.delta_vs_comparison != null ? `${o.delta_vs_comparison >= 0 ? "+" : ""}${fmt(o.delta_vs_comparison, 2)}` : "—"}</span>
                      {" "}· cost {fmtBRL(o.actual_cost)}
                    </div>
                  </div>
                  <ConfidencePill value={o.confidence} />
                  <ChevronRight className="size-4 text-slate-300 group-hover:text-slate-500" />
                </Link>
              </li>
            ))}
          </ul>
        )}
        <p className="mt-4 text-[11px] text-slate-400">Outcomes indicate association, not proof of causation, and do not represent realized savings.</p>
      </div>
    </div>
  );
}

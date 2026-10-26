"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, ClipboardCheck, Scale, ShieldAlert, Wheat } from "lucide-react";
import Link from "next/link";
import { CartesianGrid, Legend, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import type { OutcomeDetail } from "@/lib/types";
import { fmt, fmtBRL, fmtDate } from "@/lib/utils";
import { ConfidencePill } from "../intel/assessment-cards";
import { DemoBadge } from "../ui/demo-badge";
import { Card, Kpi, PageHeader } from "../ui/page";
import { ErrorState, Loading } from "../ui/states";
import { FieldNdviSvg, NdviLegend } from "./field-ndvi-svg";

const signed = (v: number | null | undefined, d = 2) => (v == null ? "—" : `${v >= 0 ? "+" : "−"}${fmt(Math.abs(v), d)}`);
const dm = (iso: string) => fmtDate(iso, { day: "2-digit", month: "2-digit" });

export function OutcomeReport({ outcomeId }: { outcomeId: number }) {
  const q = useQuery({ queryKey: ["outcome", outcomeId], queryFn: () => api.outcome(outcomeId) });
  if (q.isLoading) return <Loading label="Loading report…" />;
  if (q.error || !q.data) return <ErrorState error={q.error ?? "Outcome not found"} onRetry={() => q.refetch()} />;
  const r = q.data;
  const o = r.outcome;
  const simulated = r.series.some((p) => p.simulated);

  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader
        back={<Link href="/outcomes" className="mb-2 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-slate-800"><ArrowLeft className="size-3.5" /> Outcomes</Link>}
        title={`Intervention outcome — ${r.field_name}`}
        subtitle={<>{r.intervention.approved_action} · executed on {fmtDate(r.intervention.executed_at)}</>}
        right={<>{simulated ? <DemoBadge label="Simulated post-intervention observations" /> : <DemoBadge />}<ConfidencePill value={o.confidence} /></>}
      />
      <div className="space-y-4 p-6">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Kpi label="Treated zone NDVI" value={<span className="flex items-center gap-1.5">{fmt(o.before_value, 2)}<ArrowRight className="size-4 text-slate-400" />{fmt(o.after_value, 2)}</span>} hint={`change ${signed(o.delta)}`} />
          <Kpi label="Comparison area" value={<span className="flex items-center gap-1.5">{fmt(o.comparison_before, 2)}<ArrowRight className="size-4 text-slate-400" />{fmt(o.comparison_after, 2)}</span>} hint={`change ${signed(o.comparison_after != null && o.comparison_before != null ? o.comparison_after - o.comparison_before : null)}`} />
          <Kpi label="Net gain (difference-in-differences)" value={signed(o.delta_vs_comparison)} accent={(o.delta_vs_comparison ?? 0) > 0 ? "#23824a" : "#e0362c"} hint="zone − comparison, same period" />
          <Kpi label="Actual cost" value={fmtBRL(r.intervention.actual_cost)} hint={`approved by ${r.intervention.approved_by.split(" (")[0]}`} />
        </div>

        <Card title="Mean NDVI: treated zone vs. comparison area">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={r.series} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
              <CartesianGrid stroke="#eef2f6" vertical={false} />
              <XAxis dataKey="date" tickFormatter={dm} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} />
              <YAxis domain={["auto", "auto"]} tick={{ fontSize: 10, fill: "#64748b" }} tickLine={false} axisLine={false} tickFormatter={(v) => fmt(v, 2)} />
              {simulated && <ReferenceArea x1={r.series.find((p) => p.simulated)?.date} x2={r.series.at(-1)?.date} fill="#7c3aed" fillOpacity={0.06} label={{ value: "simulated", position: "insideTopRight", fontSize: 10, fill: "#6d28d9" }} />}
              <ReferenceLine x={nearest(r, r.intervention.executed_at)} stroke="#0a1120" strokeDasharray="3 3" label={{ value: "intervention", position: "insideTopLeft", fontSize: 10, fill: "#0a1120" }} />
              <Tooltip contentStyle={{ fontSize: 11, borderRadius: 8 }} labelFormatter={(l) => fmtDate(String(l))} formatter={(v, n) => [fmt(v as number, 3), n]} />
              <Legend wrapperStyle={{ fontSize: 11 }} iconType="plainline" />
              <Line dataKey="comparison" name={`Comparison (${r.comparison_cells} cells)`} stroke="#64748b" strokeWidth={2} strokeDasharray="4 3" dot={false} connectNulls isAnimationActive={false} />
              <Line dataKey="zone" name={`Treated zone (${r.zone_cells} cells)`} stroke="#23824a" strokeWidth={2.4} dot={{ r: 2.5, strokeWidth: 0, fill: "#23824a" }} connectNulls isAnimationActive={false} />
            </LineChart>
          </ResponsiveContainer>
          <p className="mt-1 text-[11px] text-slate-500">End-of-cycle senescence lowers NDVI in both areas; the outcome is the difference between the two declines.</p>
        </Card>

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_minmax(0,1.2fr)]">
          <FieldNdviSvg farmId={r.farm_id} fieldId={r.field_id} date={r.before_date} zoneIds={r.zone_cell_ids} title="Before" />
          <FieldNdviSvg farmId={r.farm_id} fieldId={r.field_id} date={r.after_date} zoneIds={r.zone_cell_ids} title="After" />
          <Card title="How it was measured">
            <dl className="space-y-3 text-xs leading-relaxed text-slate-700">
              <div><dt className="flex items-center gap-1.5 font-semibold text-slate-900"><Scale className="size-3.5" /> Method</dt><dd className="mt-0.5">{o.method}</dd></div>
              <div><dt className="flex items-center gap-1.5 font-semibold text-slate-900"><Wheat className="size-3.5" /> Comparison area</dt><dd className="mt-0.5">{o.comparison_area}</dd></div>
              <div><dt className="font-semibold text-slate-900">Windows</dt><dd className="mt-0.5">Before: {fmtDate(o.before_start)}–{fmtDate(o.before_end)} · After: {fmtDate(o.after_start)}–{fmtDate(o.after_end)}</dd></div>
              <div className="rounded-lg bg-amber-50 p-2.5 text-amber-900"><dt className="flex items-center gap-1.5 font-semibold"><ShieldAlert className="size-3.5" /> Limitations</dt><dd className="mt-0.5">{o.limitations}</dd></div>
            </dl>
          </Card>
        </div>
        <NdviLegend />

        {r.inspection && (
          <Card title="Evidence chain">
            <ol className="grid gap-3 text-xs md:grid-cols-3">
              <li className="rounded-lg bg-slate-50 p-3"><div className="mb-1 flex items-center gap-1.5 font-semibold"><ClipboardCheck className="size-3.5" /> Inspection {fmtDate(r.inspection.inspected_at)}</div>Verified cause: <strong>{r.inspection.verified_cause ?? "not confirmed"}</strong>. {r.inspection.findings}</li>
              <li className="rounded-lg bg-slate-50 p-3"><div className="mb-1 font-semibold">Intervention {fmtDate(r.intervention.executed_at)}</div>{r.intervention.approved_action} Cost {fmtBRL(r.intervention.actual_cost)}.</li>
              <li className="rounded-lg bg-slate-50 p-3"><div className="mb-1 font-semibold">Outcome</div>Net NDVI gain {signed(o.delta_vs_comparison)} vs. comparison. {r.disclaimer}</li>
            </ol>
            <div className="mt-3 flex gap-3 text-xs">
              {r.task && <Link href={`/tasks/${r.task.id}`} className="font-medium text-brand-700 hover:underline">View task #{r.task.id}</Link>}
              <Link href={`/fields/${r.field_id}`} className="font-medium text-brand-700 hover:underline">{r.field_code} memory</Link>
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}

function nearest(r: OutcomeDetail, iso: string) {
  return r.series.reduce((best, p) => (Math.abs(+new Date(p.date) - +new Date(iso)) < Math.abs(+new Date(best) - +new Date(iso)) ? p.date : best), r.series[0]?.date);
}

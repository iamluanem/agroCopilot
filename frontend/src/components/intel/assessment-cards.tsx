"use client";
import { AlertCircle, ArrowRight, Calculator, CheckCircle2, CircleHelp, Lightbulb, Search, ShieldAlert } from "lucide-react";
import { useState } from "react";
import type { Assessment, Confidence, Economics, HypothesisT } from "@/lib/types";
import { cn, fmt, fmtBRL, fmtHa } from "@/lib/utils";
import { Badge } from "../ui/badge";

const CONF_TONE: Record<Confidence, string> = {
  high: "bg-slate-800 text-white",
  moderate: "bg-slate-200 text-slate-800",
  low: "bg-slate-100 text-slate-500",
};

export function ConfidencePill({ value, label = "Confidence" }: { value: Confidence; label?: string }) {
  const dots = { low: 1, moderate: 2, high: 3 }[value];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium", CONF_TONE[value])} title={`${label}: ${value}`}>
      <span className="flex gap-0.5">{[1, 2, 3].map((i) => <span key={i} className={cn("size-1.5 rounded-full", i <= dots ? "bg-current" : "bg-current opacity-25")} />)}</span>
      {label} {value}
    </span>
  );
}

export function ObservationBlock({ a }: { a: Assessment }) {
  if (!a.has_zone) return <p className="rounded-lg bg-emerald-50 p-3 text-xs text-emerald-800">{a.summary}</p>;
  return (
    <div className="space-y-2">
      <div className="flex items-start gap-2 text-xs leading-relaxed text-slate-700">
        <Search className="mt-0.5 size-3.5 shrink-0 text-slate-400" />
        <p><span className="font-semibold text-slate-900">Observation. </span>{a.observation}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {a.confidence && <ConfidencePill value={a.confidence} label="Signal confidence" />}
        <Badge>{a.stage}</Badge>
        {a.onset_das != null && <Badge>Since DAS {a.onset_das}</Badge>}
        {a.worsening && <Badge tone="red">Worsening</Badge>}
      </div>
    </div>
  );
}

export function HypothesesList({ items, compact = false }: { items: HypothesisT[]; compact?: boolean }) {
  const [open, setOpen] = useState<number | null>(compact ? null : 1);
  return (
    <ol className="space-y-1.5">
      {items.map((h) => {
        const expanded = open === h.rank;
        return (
          <li key={h.rank} className={cn("rounded-lg border transition", expanded ? "border-slate-300 bg-white" : "border-slate-200 bg-slate-50/60")}>
            <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(expanded ? null : h.rank)} aria-expanded={expanded}>
              <span className={cn("grid size-5 shrink-0 place-items-center rounded-full text-[10px] font-bold", h.rank === 1 ? "bg-slate-900 text-white" : "bg-slate-200 text-slate-600")}>{h.rank}</span>
              <span className={cn("flex-1 text-xs", h.rank === 1 ? "font-semibold text-slate-900" : "text-slate-700")}>{h.cause}</span>
              <ConfidencePill value={h.confidence} label="" />
            </button>
            {expanded && (
              <div className="space-y-2.5 border-t border-slate-100 px-3 pb-3 pt-2 text-xs">
                <div>
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Evidence</div>
                  {h.evidence.length ? (
                    <ul className="space-y-1">
                      {h.evidence.map((e) => {
                        const contra = e.startsWith("Against:");
                        return (
                          <li key={e} className="flex gap-1.5 leading-snug text-slate-700">
                            {contra ? <AlertCircle className="mt-0.5 size-3 shrink-0 text-red-500" /> : <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-emerald-600" />}
                            {contra ? e.replace("Against: ", "") : e}
                          </li>
                        );
                      })}
                    </ul>
                  ) : <p className="text-slate-400">No specific evidence in the available data.</p>}
                </div>
                <div>
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Data needed to confirm</div>
                  <ul className="space-y-1">
                    {h.missing.map((m) => (
                      <li key={m} className="flex gap-1.5 leading-snug text-slate-600"><CircleHelp className="mt-0.5 size-3 shrink-0 text-amber-500" />{m}</li>
                    ))}
                  </ul>
                </div>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function NextStep({ text }: { text: string }) {
  return (
    <div className="flex gap-2 rounded-lg bg-brand-50 p-3 text-xs leading-relaxed text-brand-700 ring-1 ring-brand-100">
      <Lightbulb className="mt-0.5 size-3.5 shrink-0" />
      <p><span className="font-semibold">Suggested next action. </span>{text}</p>
    </div>
  );
}

export function EconomicsCard({ e }: { e: Economics }) {
  const [show, setShow] = useState(false);
  const a = e.assumptions;
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Estimated exposure</div>
        <button onClick={() => setShow((v) => !v)} className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-800">
          <Calculator className="size-3" /> {show ? "Hide calculation" : "Show calculation"}
        </button>
      </div>
      <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
        {fmtBRL(e.exposure_min)} <span className="text-slate-400">–</span> {fmtBRL(e.exposure_max)}
      </div>
      <div className="text-[11px] text-slate-500">
        {e.label.replace("Estimated exposure ", "")} · over {fmtHa(e.affected_ha)} affected · gross value {fmtBRL(e.gross_value_brl)}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-500">Inspection cost</div><div className="font-semibold">{fmtBRL(e.inspection_cost)}</div></div>
        <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-500">Estimated intervention</div><div className="font-semibold">{fmtBRL(e.intervention_cost)}</div></div>
      </div>
      {show && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-[11px] text-slate-600">
          <p className="leading-relaxed">{e.formula}</p>
          <table className="w-full">
            <tbody className="[&_td]:py-0.5">
              <tr><td>Critical area</td><td className="text-right font-medium">{fmtHa(a.critical_area_ha)}</td></tr>
              <tr><td>Watch area × {fmt(a.watch_area_weight * 100, 0)}%</td><td className="text-right font-medium">{fmtHa(a.watch_area_ha)}</td></tr>
              <tr><td>Expected yield</td><td className="text-right font-medium">{fmt(a.expected_yield_bags_ha, 0)} bags/ha</td></tr>
              <tr><td>Price per 60 kg bag</td><td className="text-right font-medium">{fmtBRL(a.bag_price_brl)}</td></tr>
              <tr><td>Loss range</td><td className="text-right font-medium">{fmt(a.loss_min_pct, 0)}% – {fmt(a.loss_max_pct, 0)}%</td></tr>
              <tr><td>Intervention per ha</td><td className="text-right font-medium">{fmtBRL(a.intervention_cost_brl_ha)}</td></tr>
            </tbody>
          </table>
          <p className="text-slate-400">Assumptions editable in Settings. An estimate — not a confirmed loss nor realized savings.</p>
        </div>
      )}
    </div>
  );
}

export function Disclaimer({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <p className="flex gap-1.5 text-[11px] leading-snug text-slate-500">
      <ShieldAlert className="mt-0.5 size-3 shrink-0" />{text}
    </p>
  );
}

export function AssessmentPanel({ a, compact = false, footer }: { a: Assessment; compact?: boolean; footer?: React.ReactNode }) {
  return (
    <div className="space-y-4">
      <ObservationBlock a={a} />
      {a.has_zone && (
        <>
          <div>
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Hypotheses (not a diagnosis)</h4>
            <HypothesesList items={a.hypotheses} compact={compact} />
          </div>
          {a.next_step && <NextStep text={a.next_step} />}
          {a.economics && <EconomicsCard e={a.economics} />}
          {a.priority_formula && (
            <details className="text-[11px] text-slate-500">
              <summary className="cursor-pointer font-medium text-slate-600">
                Priority {fmt(a.priority_score, 0)} · urgency {fmt(a.urgency, 2)}
              </summary>
              <p className="mt-1 leading-relaxed">{a.priority_formula}. Urgency: {a.urgency_reason}.</p>
            </details>
          )}
          <Disclaimer text={a.disclaimer} />
          {footer}
        </>
      )}
    </div>
  );
}

export function LinkArrow({ children }: { children: React.ReactNode }) {
  return <span className="inline-flex items-center gap-1">{children}<ArrowRight className="size-3" /></span>;
}

"use client";
import { AlertCircle, ArrowRight, Calculator, CheckCircle2, CircleHelp, Lightbulb, Search, ShieldAlert } from "lucide-react";
import { useState } from "react";
import type { Assessment, Confidence, Economics, HypothesisT } from "@/lib/types";
import { cn, fmt, fmtBRL, fmtHa } from "@/lib/utils";
import { Badge } from "../ui/badge";

const CONF_TONE: Record<Confidence, string> = {
  alta: "bg-slate-800 text-white",
  moderada: "bg-slate-200 text-slate-800",
  baixa: "bg-slate-100 text-slate-500",
};

export function ConfidencePill({ value, label = "Confiança" }: { value: Confidence; label?: string }) {
  const dots = { baixa: 1, moderada: 2, alta: 3 }[value];
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
        <p><span className="font-semibold text-slate-900">Observação. </span>{a.observation}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {a.confidence && <ConfidencePill value={a.confidence} label="Confiança do sinal" />}
        <Badge>{a.stage}</Badge>
        {a.onset_das != null && <Badge>Desde DAS {a.onset_das}</Badge>}
        {a.worsening && <Badge tone="vermelho">Piorando</Badge>}
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
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Evidências</div>
                  {h.evidence.length ? (
                    <ul className="space-y-1">
                      {h.evidence.map((e) => {
                        const contra = e.startsWith("Contra:");
                        return (
                          <li key={e} className="flex gap-1.5 leading-snug text-slate-700">
                            {contra ? <AlertCircle className="mt-0.5 size-3 shrink-0 text-red-500" /> : <CheckCircle2 className="mt-0.5 size-3 shrink-0 text-emerald-600" />}
                            {contra ? e.replace("Contra: ", "") : e}
                          </li>
                        );
                      })}
                    </ul>
                  ) : <p className="text-slate-400">Sem evidência específica nos dados disponíveis.</p>}
                </div>
                <div>
                  <div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Dado que falta para confirmar</div>
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
      <p><span className="font-semibold">Próxima ação sugerida. </span>{text}</p>
    </div>
  );
}

export function EconomicsCard({ e }: { e: Economics }) {
  const [show, setShow] = useState(false);
  const a = e.assumptions;
  return (
    <div className="rounded-xl border border-slate-200 p-4">
      <div className="flex items-center justify-between">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-slate-500">Exposição estimada</div>
        <button onClick={() => setShow((v) => !v)} className="inline-flex shrink-0 items-center gap-1 text-[11px] font-medium text-slate-500 hover:text-slate-800">
          <Calculator className="size-3" /> {show ? "Ocultar cálculo" : "Ver cálculo"}
        </button>
      </div>
      <div className="mt-1 text-xl font-semibold tracking-tight text-slate-900">
        {fmtBRL(e.exposure_min)} <span className="text-slate-400">–</span> {fmtBRL(e.exposure_max)}
      </div>
      <div className="text-[11px] text-slate-500">
        {e.label.replace("Exposição estimada ", "")} · sobre {fmtHa(e.affected_ha)} afetados · valor bruto {fmtBRL(e.gross_value_rs)}
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-500">Custo da vistoria</div><div className="font-semibold">{fmtBRL(e.inspection_cost)}</div></div>
        <div className="rounded-lg bg-slate-50 p-2"><div className="text-[10px] text-slate-500">Intervenção estimada</div><div className="font-semibold">{fmtBRL(e.intervention_cost)}</div></div>
      </div>
      {show && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3 text-[11px] text-slate-600">
          <p className="leading-relaxed">{e.formula}</p>
          <table className="w-full">
            <tbody className="[&_td]:py-0.5">
              <tr><td>Área crítica</td><td className="text-right font-medium">{fmtHa(a.area_critica_ha)}</td></tr>
              <tr><td>Área em atenção × {fmt(a.peso_area_atencao * 100, 0)}%</td><td className="text-right font-medium">{fmtHa(a.area_atencao_ha)}</td></tr>
              <tr><td>Produtividade esperada</td><td className="text-right font-medium">{fmt(a.produtividade_esperada_sc_ha, 0)} sc/ha</td></tr>
              <tr><td>Preço da saca</td><td className="text-right font-medium">{fmtBRL(a.preco_saca_rs)}</td></tr>
              <tr><td>Faixa de perda</td><td className="text-right font-medium">{fmt(a.perda_min_pct, 0)}% – {fmt(a.perda_max_pct, 0)}%</td></tr>
              <tr><td>Intervenção por ha</td><td className="text-right font-medium">{fmtBRL(a.custo_intervencao_rs_ha)}</td></tr>
            </tbody>
          </table>
          <p className="text-slate-400">Premissas editáveis em Configurações. Estimativa, não perda confirmada nem economia realizada.</p>
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
            <h4 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-500">Hipóteses (não diagnóstico)</h4>
            <HypothesesList items={a.hypotheses} compact={compact} />
          </div>
          {a.next_step && <NextStep text={a.next_step} />}
          {a.economics && <EconomicsCard e={a.economics} />}
          {a.priority_formula && (
            <details className="text-[11px] text-slate-500">
              <summary className="cursor-pointer font-medium text-slate-600">
                Prioridade {fmt(a.priority_score, 0)} · urgência {fmt(a.urgency, 2)}
              </summary>
              <p className="mt-1 leading-relaxed">{a.priority_formula}. Urgência: {a.urgency_reason}.</p>
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

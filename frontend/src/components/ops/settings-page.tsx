"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Coins, Gauge, Loader2, RotateCcw, Satellite, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EconomicsCfg, ProviderChoice, RiskCfg } from "@/lib/types";
import { cn, fmt, fmtBRL, fmtDate } from "@/lib/utils";
import { DemoBadge } from "../ui/demo-badge";
import { Card, PageHeader } from "../ui/page";
import { ErrorState, Loading } from "../ui/states";

const inp = "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm tabular-nums outline-none focus:ring-2 focus:ring-brand-500/30";

function Num({ label, value, onChange, step = 1, suffix, hint }: { label: string; value: number; onChange: (v: number) => void; step?: number; suffix?: string; hint?: string }) {
  return (
    <label className="block text-xs font-medium text-slate-600">
      {label}
      <div className="relative mt-1">
        <input type="number" step={step} value={Number.isFinite(value) ? value : ""} onChange={(e) => onChange(Number(e.target.value))} className={cn(inp, suffix && "pr-14")} />
        {suffix && <span className="pointer-events-none absolute inset-y-0 right-3 grid place-items-center text-xs text-slate-400">{suffix}</span>}
      </div>
      {hint && <span className="mt-1 block text-[11px] font-normal text-slate-400">{hint}</span>}
    </label>
  );
}

const PROVIDERS: { v: ProviderChoice; label: string; desc: string }[] = [
  { v: "auto", label: "Automatic", desc: "Uses the available key; without a key, demo mode" },
  { v: "demo", label: "Demo (rules)", desc: "Deterministic, no cost — ideal for recording" },
  { v: "anthropic", label: "Claude", desc: "Requires ANTHROPIC_API_KEY in .env" },
  { v: "openai", label: "OpenAI", desc: "Requires OPENAI_API_KEY in .env" },
];

export function SettingsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
  const imagery = useQuery({ queryKey: ["imagery", farms.data?.[0]?.id], queryFn: () => api.imagery(farms.data![0].id), enabled: !!farms.data?.length });
  const [eco, setEco] = useState<EconomicsCfg | null>(null);
  const [risk, setRisk] = useState<RiskCfg | null>(null);
  const [prov, setProv] = useState<ProviderChoice>("auto");
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    if (q.data && !eco) { setEco(q.data.economics); setRisk(q.data.risk); setProv(q.data.llm_provider); }
  }, [q.data, eco]);

  const invalidateAll = () => ["risk", "priorities", "assessment", "field", "copilot-status", "tasks", "tasks-summary", "outcomes", "dates"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const save = useMutation({
    mutationFn: () => api.saveSettings({ economics: eco!, risk: risk!, llm_provider: prov }),
    onSuccess: (d) => { qc.setQueryData(["settings"], d); invalidateAll(); },
  });
  const reset = useMutation({ mutationFn: api.resetDemo, onSuccess: () => { setConfirmReset(false); invalidateAll(); } });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!eco || !risk || !q.data) return <Loading label="Loading settings…" />;
  const dirty = JSON.stringify({ eco, risk, prov }) !== JSON.stringify({ eco: q.data.economics, risk: q.data.risk, prov: q.data.llm_provider });
  const gross = eco.expected_yield_bags_ha * eco.bag_price_brl;

  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader title="Settings" subtitle="Assumptions used in the estimates, risk sensitivity and data sources." right={<DemoBadge />} />
      <div className="mx-auto grid max-w-5xl gap-4 p-6 lg:grid-cols-2">
        <Card title="Economic assumptions" right={<Coins className="size-4 text-slate-400" />}>
          <div className="grid grid-cols-2 gap-3">
            <Num label="Expected yield" value={eco.expected_yield_bags_ha} onChange={(v) => setEco({ ...eco, expected_yield_bags_ha: v })} suffix="bags/ha" hint="60 kg bags" />
            <Num label="Price per bag" value={eco.bag_price_brl} onChange={(v) => setEco({ ...eco, bag_price_brl: v })} suffix="R$" />
            <Num label="Minimum loss" value={eco.loss_min_pct} onChange={(v) => setEco({ ...eco, loss_min_pct: v })} suffix="%" />
            <Num label="Maximum loss" value={eco.loss_max_pct} onChange={(v) => setEco({ ...eco, loss_max_pct: v })} suffix="%" />
            <Num label="Cost per inspection" value={eco.inspection_cost_brl} onChange={(v) => setEco({ ...eco, inspection_cost_brl: v })} suffix="R$" step={10} />
            <Num label="Intervention per hectare" value={eco.intervention_cost_brl_ha} onChange={(v) => setEco({ ...eco, intervention_cost_brl_ha: v })} suffix="R$/ha" step={5} />
          </div>
          <p className="mt-3 rounded-lg bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
            Gross value per hectare: <strong>{fmtBRL(gross)}</strong>. Exposure per affected hectare: <strong>{fmtBRL(gross * eco.loss_min_pct / 100)} – {fmtBRL(gross * eco.loss_max_pct / 100)}</strong>. A risk estimate, not a confirmed loss.
          </p>
        </Card>

        <Card title="Risk sensitivity" right={<Gauge className="size-4 text-slate-400" />}>
          <div className="grid grid-cols-2 gap-3">
            <Num label="Watch threshold (score)" value={risk.yellow_threshold} onChange={(v) => setRisk({ ...risk, yellow_threshold: v })} step={0.1} hint="Robust deviations below expected" />
            <Num label="Critical threshold (score)" value={risk.red_threshold} onChange={(v) => setRisk({ ...risk, red_threshold: v })} step={0.1} hint="Must be greater than the watch threshold" />
          </div>
          <label className="mt-3 block text-xs font-medium text-slate-600">
            Cell history weight: {fmt(risk.history_weight * 100, 0)}% · field median: {fmt((1 - risk.history_weight) * 100, 0)}%
            <input type="range" min={0} max={1} step={0.05} value={risk.history_weight} onChange={(e) => setRisk({ ...risk, history_weight: Number(e.target.value) })} className="mt-2 w-full accent-brand-600" />
          </label>
          <p className="mt-2 text-[11px] text-slate-400">Changing thresholds recalculates every date (≈10 s on the first query). Tasks and outcomes already created keep their original assessment.</p>
        </Card>

        <Card title="Copilot" right={<Bot className="size-4 text-slate-400" />}>
          <div className="grid gap-2 sm:grid-cols-2">
            {PROVIDERS.map((p) => {
              const unavailable = (p.v === "anthropic" || p.v === "openai") && !q.data.copilot.available[p.v];
              return (
                <button key={p.v} onClick={() => setProv(p.v)} className={cn("rounded-xl border p-3 text-left transition", prov === p.v ? "border-navy-900 ring-2 ring-navy-900/10" : "border-slate-200 hover:border-slate-300")}>
                  <div className="flex items-center justify-between text-sm font-semibold">{p.label}{unavailable && <span className="text-[10px] font-normal text-amber-700">no key</span>}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">{p.desc}</div>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-slate-500">In use now: <strong>{q.data.copilot.label}</strong>. Without a key, the chosen provider falls back to demo mode with a warning.</p>
        </Card>

        <Card title="Data sources" right={<Satellite className="size-4 text-slate-400" />}>
          <ul className="space-y-2 text-xs">
            <li className="flex items-start gap-2"><span className="mt-1 size-2 rounded-full bg-violet-500" /><span><strong>Demo data</strong> — synthetic, deterministic fields, NDVI/NDRE, weather and history.</span></li>
            <li className="flex items-start gap-2"><span className="mt-1 size-2 rounded-full bg-emerald-600" /><span><strong>Real Sentinel-2</strong> — {imagery.data?.length ? (
              <>scene from {fmtDate(imagery.data[0].date)} ({fmt(imagery.data[0].cloud_cover, 1)}% cloud), available as a layer on the Map.</>
            ) : <>no scene downloaded yet.</>}</span></li>
          </ul>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-navy-950 p-3 text-[11px] leading-relaxed text-slate-200">docker compose exec api python scripts/fetch_sentinel.py</pre>
          <p className="mt-2 text-[11px] text-slate-400">Finds the least cloudy scene of the last 120 days on Earth Search (free, no key), masks clouds and builds NDVI and NDRE.</p>
        </Card>

        <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
          <button disabled={!dirty || save.isPending} onClick={() => save.mutate()} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40">
            {save.isPending ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />} Save and recalculate
          </button>
          {dirty && <button onClick={() => { setEco(q.data.economics); setRisk(q.data.risk); setProv(q.data.llm_provider); }} className="text-sm text-slate-500 hover:text-slate-800">Discard changes</button>}
          {save.isSuccess && !dirty && <span className="text-xs text-emerald-700">Saved. Priorities and exposures recalculated.</span>}
          {save.error && <span className="text-xs text-red-600">{(save.error as Error).message}</span>}
        </div>

        <Card title="Demo" className="border-amber-200 lg:col-span-2">
          <div className="flex flex-wrap items-center gap-3">
            <p className="flex-1 text-xs text-slate-600">Removes tasks, inspections, interventions and simulated observations created during the demo. The original synthetic scenario and settings are kept.</p>
            {!confirmReset ? (
              <button onClick={() => setConfirmReset(true)} className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"><RotateCcw className="size-3.5" /> Reset demo</button>
            ) : (
              <span className="flex items-center gap-2">
                <TriangleAlert className="size-4 text-amber-600" /><span className="text-xs text-slate-700">Confirm?</span>
                <button onClick={() => reset.mutate()} disabled={reset.isPending} className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700">{reset.isPending ? "Resetting…" : "Yes, reset"}</button>
                <button onClick={() => setConfirmReset(false)} className="text-xs text-slate-500">Cancel</button>
              </span>
            )}
          </div>
          {reset.data && <p className="mt-2 text-xs text-emerald-700">Demo reset: {reset.data.tasks_removed} task{reset.data.tasks_removed === 1 ? "" : "s"} removed.</p>}
        </Card>
      </div>
    </div>
  );
}

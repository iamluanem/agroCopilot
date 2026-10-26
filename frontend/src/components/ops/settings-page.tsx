"use client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, CheckCircle2, Coins, Gauge, Loader2, RotateCcw, Satellite, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { EconomiaCfg, ProviderChoice, RiscoCfg } from "@/lib/types";
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
  { v: "auto", label: "Automático", desc: "Usa a chave disponível; sem chave, modo demo" },
  { v: "demo", label: "Demo (regras)", desc: "Determinístico, sem custo — ideal para gravar" },
  { v: "anthropic", label: "Claude", desc: "Requer ANTHROPIC_API_KEY no .env" },
  { v: "openai", label: "OpenAI", desc: "Requer OPENAI_API_KEY no .env" },
];

export function SettingsPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["settings"], queryFn: api.settings });
  const farms = useQuery({ queryKey: ["farms"], queryFn: api.farms });
  const imagery = useQuery({ queryKey: ["imagery", farms.data?.[0]?.id], queryFn: () => api.imagery(farms.data![0].id), enabled: !!farms.data?.length });
  const [eco, setEco] = useState<EconomiaCfg | null>(null);
  const [risk, setRisk] = useState<RiscoCfg | null>(null);
  const [prov, setProv] = useState<ProviderChoice>("auto");
  const [confirmReset, setConfirmReset] = useState(false);

  useEffect(() => {
    if (q.data && !eco) { setEco(q.data.economia); setRisk(q.data.risco); setProv(q.data.llm_provider); }
  }, [q.data, eco]);

  const invalidateAll = () => ["risk", "priorities", "assessment", "field", "copilot-status", "tasks", "tasks-summary", "outcomes", "dates"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const save = useMutation({
    mutationFn: () => api.saveSettings({ economia: eco!, risco: risk!, llm_provider: prov }),
    onSuccess: (d) => { qc.setQueryData(["settings"], d); invalidateAll(); },
  });
  const reset = useMutation({ mutationFn: api.resetDemo, onSuccess: () => { setConfirmReset(false); invalidateAll(); } });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  if (!eco || !risk || !q.data) return <Loading label="Carregando configurações…" />;
  const dirty = JSON.stringify({ eco, risk, prov }) !== JSON.stringify({ eco: q.data.economia, risk: q.data.risco, prov: q.data.llm_provider });
  const gross = eco.produtividade_esperada_sc_ha * eco.preco_saca_rs;

  return (
    <div className="flex-1 overflow-y-auto">
      <PageHeader title="Configurações" subtitle="Premissas usadas nas estimativas, sensibilidade do risco e fontes de dados." right={<DemoBadge />} />
      <div className="mx-auto grid max-w-5xl gap-4 p-6 lg:grid-cols-2">
        <Card title="Premissas econômicas" right={<Coins className="size-4 text-slate-400" />}>
          <div className="grid grid-cols-2 gap-3">
            <Num label="Produtividade esperada" value={eco.produtividade_esperada_sc_ha} onChange={(v) => setEco({ ...eco, produtividade_esperada_sc_ha: v })} suffix="sc/ha" />
            <Num label="Preço da saca" value={eco.preco_saca_rs} onChange={(v) => setEco({ ...eco, preco_saca_rs: v })} suffix="R$" />
            <Num label="Perda mínima" value={eco.perda_min_pct} onChange={(v) => setEco({ ...eco, perda_min_pct: v })} suffix="%" />
            <Num label="Perda máxima" value={eco.perda_max_pct} onChange={(v) => setEco({ ...eco, perda_max_pct: v })} suffix="%" />
            <Num label="Custo por vistoria" value={eco.custo_vistoria_rs} onChange={(v) => setEco({ ...eco, custo_vistoria_rs: v })} suffix="R$" step={10} />
            <Num label="Intervenção por hectare" value={eco.custo_intervencao_rs_ha} onChange={(v) => setEco({ ...eco, custo_intervencao_rs_ha: v })} suffix="R$/ha" step={5} />
          </div>
          <p className="mt-3 rounded-lg bg-slate-50 p-3 text-[11px] leading-relaxed text-slate-600">
            Valor bruto por hectare: <strong>{fmtBRL(gross)}</strong>. Exposição por hectare afetado: <strong>{fmtBRL(gross * eco.perda_min_pct / 100)} – {fmtBRL(gross * eco.perda_max_pct / 100)}</strong>. É estimativa de risco, não perda confirmada.
          </p>
        </Card>

        <Card title="Sensibilidade do risco" right={<Gauge className="size-4 text-slate-400" />}>
          <div className="grid grid-cols-2 gap-3">
            <Num label="Limiar de atenção (score)" value={risk.limiar_amarelo} onChange={(v) => setRisk({ ...risk, limiar_amarelo: v })} step={0.1} hint="Desvios robustos abaixo do esperado" />
            <Num label="Limiar crítico (score)" value={risk.limiar_vermelho} onChange={(v) => setRisk({ ...risk, limiar_vermelho: v })} step={0.1} hint="Precisa ser maior que o de atenção" />
          </div>
          <label className="mt-3 block text-xs font-medium text-slate-600">
            Peso do histórico da célula: {fmt(risk.peso_historico * 100, 0)}% · mediana do talhão: {fmt((1 - risk.peso_historico) * 100, 0)}%
            <input type="range" min={0} max={1} step={0.05} value={risk.peso_historico} onChange={(e) => setRisk({ ...risk, peso_historico: Number(e.target.value) })} className="mt-2 w-full accent-brand-600" />
          </label>
          <p className="mt-2 text-[11px] text-slate-400">Mudar limiares recalcula todas as datas (≈10 s na primeira consulta). Tarefas e resultados já criados mantêm a avaliação original.</p>
        </Card>

        <Card title="Copiloto" right={<Bot className="size-4 text-slate-400" />}>
          <div className="grid gap-2 sm:grid-cols-2">
            {PROVIDERS.map((p) => {
              const unavailable = (p.v === "anthropic" || p.v === "openai") && !q.data.copilot.available[p.v];
              return (
                <button key={p.v} onClick={() => setProv(p.v)} className={cn("rounded-xl border p-3 text-left transition", prov === p.v ? "border-navy-900 ring-2 ring-navy-900/10" : "border-slate-200 hover:border-slate-300")}>
                  <div className="flex items-center justify-between text-sm font-semibold">{p.label}{unavailable && <span className="text-[10px] font-normal text-amber-700">sem chave</span>}</div>
                  <div className="mt-0.5 text-[11px] text-slate-500">{p.desc}</div>
                </button>
              );
            })}
          </div>
          <p className="mt-3 text-[11px] text-slate-500">Em uso agora: <strong>{q.data.copilot.label}</strong>. Sem chave, o provedor escolhido cai para o modo demo com aviso.</p>
        </Card>

        <Card title="Fontes de dados" right={<Satellite className="size-4 text-slate-400" />}>
          <ul className="space-y-2 text-xs">
            <li className="flex items-start gap-2"><span className="mt-1 size-2 rounded-full bg-violet-500" /><span><strong>Dados de demonstração</strong> — talhões, NDVI/NDRE, clima e histórico sintéticos e determinísticos.</span></li>
            <li className="flex items-start gap-2"><span className="mt-1 size-2 rounded-full bg-emerald-600" /><span><strong>Sentinel-2 real</strong> — {imagery.data?.length ? (
              <>cena de {fmtDate(imagery.data[0].date)} (nuvem {fmt(imagery.data[0].cloud_cover, 1)}%), disponível como camada no Mapa.</>
            ) : <>nenhuma cena baixada ainda.</>}</span></li>
          </ul>
          <pre className="mt-3 overflow-x-auto rounded-lg bg-navy-950 p-3 text-[11px] leading-relaxed text-slate-200">docker compose exec api python scripts/fetch_sentinel.py</pre>
          <p className="mt-2 text-[11px] text-slate-400">Busca a cena com menos nuvem dos últimos 120 dias no Earth Search (gratuito, sem chave), mascara nuvens e gera NDVI e NDRE.</p>
        </Card>

        <div className="flex flex-wrap items-center gap-3 lg:col-span-2">
          <button disabled={!dirty || save.isPending} onClick={() => save.mutate()} className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40">
            {save.isPending ? <Loader2 className="size-4 animate-spin" /> : <CheckCircle2 className="size-4" />} Salvar e recalcular
          </button>
          {dirty && <button onClick={() => { setEco(q.data.economia); setRisk(q.data.risco); setProv(q.data.llm_provider); }} className="text-sm text-slate-500 hover:text-slate-800">Descartar alterações</button>}
          {save.isSuccess && !dirty && <span className="text-xs text-emerald-700">Salvo. Prioridades e exposições recalculadas.</span>}
          {save.error && <span className="text-xs text-red-600">{(save.error as Error).message}</span>}
        </div>

        <Card title="Demonstração" className="border-amber-200 lg:col-span-2">
          <div className="flex flex-wrap items-center gap-3">
            <p className="flex-1 text-xs text-slate-600">Remove tarefas, vistorias, intervenções e observações simuladas criadas durante a demo. O cenário sintético original e as configurações são mantidos.</p>
            {!confirmReset ? (
              <button onClick={() => setConfirmReset(true)} className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100"><RotateCcw className="size-3.5" /> Reiniciar demo</button>
            ) : (
              <span className="flex items-center gap-2">
                <TriangleAlert className="size-4 text-amber-600" /><span className="text-xs text-slate-700">Confirma?</span>
                <button onClick={() => reset.mutate()} disabled={reset.isPending} className="rounded-lg bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700">{reset.isPending ? "Reiniciando…" : "Sim, reiniciar"}</button>
                <button onClick={() => setConfirmReset(false)} className="text-xs text-slate-500">Cancelar</button>
              </span>
            )}
          </div>
          {reset.data && <p className="mt-2 text-xs text-emerald-700">Demo reiniciada: {reset.data.tarefas_removidas} tarefa(s) removida(s).</p>}
        </Card>
      </div>
    </div>
  );
}
